# Copyright 1996-2021 Cyberbotics Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import copy
import json
import math
import numpy as np
import os
import random
import socket
import subprocess
import time
import traceback
import yaml

from scipy.spatial import ConvexHull

from types import SimpleNamespace

from controller import Supervisor, Node

from gamestate import GameState
from field import Field
from forceful_contact_matrix import ForcefulContactMatrix
from logging import info, warning, error, close
from geometry import distance2, rotate_along_z, aabb_circle_collision, polygon_circle_collision, update_aabb
from display import Display
from sim_time import SimTime
from blackboard import Blackboard


# game interruptions requiring a free kick procedure
GAME_INTERRUPTIONS = {
    'DIRECT_FREEKICK': 'direct free kick',
    'INDIRECT_FREEKICK': 'indirect free kick',
    'PENALTYKICK': 'penalty kick',
    'CORNERKICK': 'corner kick',
    'GOALKICK': 'goal kick',
    'THROWIN': 'throw in'
}

global game, red_team, blue_team, time_count, time_step


class Referee:
    def __init__(self):
        # start the webots supervisor
        self.supervisor = Supervisor()
        self.time_step = int(self.supervisor.getBasicTimeStep())
        self.sim_time = SimTime()
        with open('referee_config.yaml') as f:
            config = yaml.load(f)
        self.config = SimpleNamespace(**config)
        self.config.GOAL_HALF_WIDTH = self.config.GOAL_WIDTH / 2

        # determine configuration file name
        game_config_file = os.environ['WEBOTS_ROBOCUP_GAME'] if 'WEBOTS_ROBOCUP_GAME' in os.environ \
            else os.path.join(os.getcwd(), 'game.json')
        if not os.path.isfile(game_config_file):
            error(f'Cannot read {game_config_file} game config file.')
            self.clean_exit()
        # read configuration files
        with open(game_config_file) as json_file:
            self.game = json.loads(json_file.read(), object_hook=lambda d: Game(**d))
        self.red_team = self.read_team(game.red.config)
        self.blue_team = self.read_team(game.blue.config)

        self.blackboard = Blackboard(self.supervisor, self.game, self.sim_time, self.config)
        self.others = []
        self.game_controller_send_id = 0
        self.game_controller_send_unanswered = {}
        self.game_controller_send_sent_once = None
        self.game_controller_udp_filter = os.environ['GAME_CONTROLLER_UDP_FILTER'] if 'GAME_CONTROLLER_UDP_FILTER' in os.environ else None


        self.setup()
        self.main_loop()

    def announce_final_score(self):
        if not hasattr(game, "state"):
            return
        red_team_idx = self.team_index('red')
        blue_team_idx = self.team_index('blue')
        red_score = game.state.teams[red_team_idx].score
        blue_score = game.state.teams[blue_team_idx].score
        # TODO: store and print score before penalty shootouts
        info(f"FINAL SCORE: {red_score}-{blue_score}")

    def clean_exit(self):
        """Save logs and clean all subprocesses"""
        self.announce_final_score()
        if hasattr(game, "controller") and game.controller:
            info("Closing 'controller' socket")
            game.controller.close()
        if hasattr(game, "controller_process") and game.controller_process:
            info("Terminating 'game_controller' process")
            game.controller_process.terminate()
        if hasattr(game, "udp_bouncer_process") and self.udp_bouncer_process:
            info("Terminating 'udp_bouncer' process")
            self.udp_bouncer_process.terminate()
        if hasattr(game, 'over') and game.over:
            info("Game is over")
            if hasattr(game, 'press_a_key_to_terminate') and game.press_a_key_to_terminate:
                print('Press a key to terminate')
                keyboard = self.supervisor.getKeyboard()
                keyboard.enable(time_step)
                while self.supervisor.step(time_step) != -1:
                    if keyboard.getKey() != -1:
                        break
            else:
                waiting_steps = self.config.END_OF_GAME_TIMEOUT * 1000 / time_step
                info(f"Waiting {waiting_steps} simulation steps before exiting")
                while waiting_steps > 0:
                    self.supervisor.step(time_step)
                    waiting_steps -= 1
                info("Finished waiting")
        if hasattr(game, 'record_simulation'):
            if game.record_simulation.endswith(".html"):
                info("Stopping animation recording")
                self.supervisor.animationStopRecording()
            elif game.record_simulation.endswith(".mp4"):
                info("Starting encoding")
                self.supervisor.movieStopRecording()
                while not self.supervisor.movieIsReady():
                    self.supervisor.step(time_step)
                info("Encoding finished")
        info("Exiting webots properly")

        # Note: If self.supervisor.step is not called before the 'simulationQuit', information is not shown
        self.supervisor.step(time_step)
        self.supervisor.simulationQuit(0)

    def perform_status_update(self):
        now = time.time()
        if not hasattr(game, "last_real_time"):
            game.last_real_time = now
            game.last_time_count = time_count
        elif now - game.last_real_time > self.config.STATUS_PRINT_PERIOD:
            elapsed_real = now - game.last_real_time
            elapsed_simulation = (time_count - game.last_time_count) / 1000
            speed_factor = elapsed_simulation / elapsed_real
            messages = [f"Avg speed factor: {speed_factor:.3f} (over last {elapsed_real:.2f} seconds)"]
            if game.state is None:
                messages.append("No messages received from GameController yet")
            else:
                messages.append(f"state: {game.state.game_state}, remaining time: {game.state.seconds_remaining}")
                if game.state.secondary_state in GAME_INTERRUPTIONS:
                    messages.append(f"  sec_state: {game.state.secondary_state} phase: {game.state.secondary_state_info[1]}")
            if game.penalty_shootout:
                messages.append(f"{self.get_penalty_shootout_msg()}")
            messages = [f"STATUS: {m}" for m in messages]
            info(messages)
            game.last_real_time = now
            game.last_time_count = time_count

    def toss_a_coin_if_needed(self, attribute):  # attribute should be either "side_left" or "kickoff"
        # If game.json contains such an attribute, use it to determine field side and kick-off
        # Supported values are "red", "blue" and "random". Default value is "random".
        if hasattr(game, attribute):
            if getattr(game, attribute) == 'red':
                setattr(game, attribute, game.red.id)
            elif getattr(game, attribute) == 'blue':
                setattr(game, attribute, game.blue.id)
            elif getattr(game, attribute) != 'random':
                error(f'Unsupported value for "{attribute}" in game.json file: {getattr(game, attribute)}, using "random".')
                setattr(game, attribute, 'random')
        else:
            setattr(game, attribute, 'random')
        if getattr(game, attribute) == 'random':  # toss a coin to determine a random team
            setattr(game, attribute, game.red.id if bool(random.getrandbits(1)) else game.blue.id)

    def spawn_team(self, team, red_on_right, children):
        color = team['color']
        nb_players = len(team['players'])
        for number in team['players']:
            player = team['players'][number]
            model = player['proto']
            n = int(number) - 1
            port = game.red.ports[n] if color == 'red' else game.blue.ports[n]
            if red_on_right:  # symmetry with respect to the central line of the field
                self.flip_poses(player)
            defname = color.upper() + '_PLAYER_' + number
            halfTimeStartingTranslation = player['halfTimeStartingPose']['translation']
            halfTimeStartingRotation = player['halfTimeStartingPose']['rotation']
            string = f'DEF {defname} {model}{{name "{color} player {number}" translation ' + \
                     f'{halfTimeStartingTranslation[0]} {halfTimeStartingTranslation[1]} {halfTimeStartingTranslation[2]} rotation ' + \
                     f'{halfTimeStartingRotation[0]} {halfTimeStartingRotation[1]} {halfTimeStartingRotation[2]} ' + \
                     f'{halfTimeStartingRotation[3]} controllerArgs ["{port}" "{nb_players}"'
            hosts = game.red.hosts if color == 'red' else game.blue.hosts
            for h in hosts:
                string += f', "{h}"'
            string += '] }}'
            children.importMFNodeFromString(-1, string)
            player['robot'] = self.supervisor.getFromDef(defname)
            player['position'] = player['robot'].getCenterOfMass()
            info(f'Spawned {defname} {model} on port {port} at halfTimeStartingPose: translation (' +
                 f'{halfTimeStartingTranslation[0]} {halfTimeStartingTranslation[1]} {halfTimeStartingTranslation[2]}), ' +
                 f'rotation ({halfTimeStartingRotation[0]} {halfTimeStartingRotation[1]} {halfTimeStartingRotation[2]} ' +
                 f'{halfTimeStartingRotation[3]}).')

    def team_index(self, color):
        if color not in ['red', 'blue']:
            raise RuntimeError(f'Wrong color passed to team_index(): \'{color}\'.')
        id = game.red.id if color == 'red' else game.blue.id
        index = 0 if game.state.teams[0].team_number == id else 1
        if game.state.teams[index].team_number != id:
            raise RuntimeError(f'Wrong team number set in team_index(): {id} != {game.state.teams[index].team_number}')
        return index

    def game_controller_receive(self):
        data = None
        ip = None
        while True:
            if self.game_controller_udp_filter and ip and ip not in self.others:
                self.others.append(ip)
                warning(f'Ignoring UDP packets from {ip} not matching GAME_CONTROLLER_UDP_FILTER={self.game_controller_udp_filter}.')
            try:
                data, peer = game.udp.recvfrom(GameState.sizeof())
                ip, port = peer
                if self.game_controller_udp_filter is None or self.game_controller_udp_filter == ip:
                    break
                else:
                    continue
            except BlockingIOError:
                return
            except Exception as e:
                error(f'UDP input failure: {e}')
                return
            if not data:
                error('No UDP data received')
                return
        self.previous_seconds_remaining = game.state.seconds_remaining if game.state else 0
        previous_secondary_seconds_remaining = game.state.secondary_seconds_remaining if game.state else 0
        previous_state = game.state.game_state if game.state else None
        previous_sec_state = game.state.secondary_state if game.state else None
        previous_sec_phase = game.state.secondary_state_info[1] if game.state else None
        if game.state:
            red = 0 if game.state.teams[0].team_color == 'RED' else 1
            blue = 1 if red == 0 else 0
            previous_red_score = game.state.teams[red].score
            previous_blue_score = game.state.teams[blue].score
        else:
            previous_red_score = 0
            previous_blue_score = 0

        game.state = GameState.parse(data)

        if previous_state != game.state.game_state:
            info(f'New state received from GameController: {game.state.game_state}.')
            if game.wait_for_state is not None:
                if 'STATE_' + game.wait_for_state != game.state.game_state:
                    warning(f'Received unexpected state from GameController: {game.state.game_state} ' +
                            f'while expecting {game.wait_for_state}')
                else:
                    info(f"State has succesfully changed to {game.wait_for_state}")
                    game.wait_for_state = None
        new_sec_state = game.state.secondary_state
        new_sec_phase = game.state.secondary_state_info[1]
        if previous_sec_state != new_sec_state or previous_sec_phase != new_sec_phase:
            info(f'New secondary state received from GameController: {new_sec_state}, phase {new_sec_phase}.')
            if game.wait_for_sec_state is not None or game.wait_for_sec_phase is not None:
                if 'STATE_' + game.wait_for_sec_state != new_sec_state or new_sec_phase != game.wait_for_sec_phase:
                    warning(f'Received unexpected secondary state from GameController: {new_sec_state}:{new_sec_phase} ' +
                            f'while expecting {game.wait_for_sec_state}:{game.wait_for_sec_phase}')
                else:
                    info(f"State has succesfully changed to {new_sec_state}:{new_sec_phase}")
                    game.wait_for_sec_state = None
                    game.wait_for_sec_phase = None
        if game.state.game_state == 'STATE_PLAYING' and \
                game.state.secondary_seconds_remaining == 0 and previous_secondary_seconds_remaining > 0:
            if game.in_play is None and game.phase == 'KICKOFF':
                info('Ball in play, can be touched by any player (10 seconds elapsed after kickoff).')
                game.in_play = time_count
                game.ball_last_move = time_count
        if self.previous_seconds_remaining != game.state.seconds_remaining:
            allow_in_play = game.wait_for_sec_state is None and game.wait_for_sec_phase is None
            if allow_in_play and game.state.secondary_state == "STATE_NORMAL" and game.interruption_seconds is not None:
                if game.interruption_seconds - game.state.seconds_remaining > IN_PLAY_TIMEOUT:
                    if game.in_play is None:
                        info('Ball in play, can be touched by any player (10 seconds elapsed).')
                        game.in_play = time_count
                        game.ball_last_move = time_count
                        game.interruption = None
                        game.interruption_step = None
                        game.interruption_step_time = 0
                        game.interruption_team = None
                        game.interruption_seconds = None
            update_time_display()
        red = 0 if game.state.teams[0].team_color == 'RED' else 1
        blue = 1 if red == 0 else 0
        if previous_red_score != game.state.teams[red].score or \
                previous_blue_score != game.state.teams[blue].score:
            update_score_display()
        # print(game.state.game_state)
        secondary_state = game.state.secondary_state
        secondary_state_info = game.state.secondary_state_info
        if secondary_state[0:6] == 'STATE_' and secondary_state[6:] in GAME_INTERRUPTIONS:
            kick = secondary_state[6:]
            step = secondary_state_info[1]
            delay = (time_count - game.interruption_step_time) / 1000
            if step == 0 and game.interruption_step != step:
                game.interruption_step = step
                game.interruption_step_time = time_count
                info(f'Awarding a {GAME_INTERRUPTIONS[kick]}.')
            elif (step == 1 and game.interruption_step != step and game.state.secondary_seconds_remaining <= 0 and
                  delay >= self.config.SIMULATED_TIME_INTERRUPTION_PHASE_1):
                game.interruption_step = step
                game_controller_send(f'{kick}:{secondary_state_info[0]}:PREPARE')
                game.interruption_step_time = time_count
                info(f'Prepare for {GAME_INTERRUPTIONS[kick]}.')
            elif step == 2 and game.interruption_step != step and game.state.secondary_seconds_remaining <= 0:
                game.interruption_step = step
                opponent_team = blue_team if secondary_state_info[0] == game.red.id else red_team
                check_team_away_from_ball(opponent_team, game.field.opponent_distance_to_ball)
                if kick == "PENALTYKICK":
                    check_penalty_kick_positions()
                game_controller_send(f'{kick}:{secondary_state_info[0]}:EXECUTE')
                info(f'Execute {GAME_INTERRUPTIONS[kick]}.')
                game.interruption_seconds = game.state.seconds_remaining
                if game.interruption_seconds == 0:
                    game.interruption_seconds = None
        elif secondary_state not in ['STATE_NORMAL', 'STATE_OVERTIME', 'STATE_PENALTYSHOOT']:
            print(f'GameController {game.state.game_state}:{secondary_state}: {secondary_state_info}')
        update_penalized()
        if previous_state != game.state.game_state or \
                previous_sec_state != new_sec_state or previous_sec_phase != new_sec_phase or \
                previous_secondary_seconds_remaining != game.state.secondary_seconds_remaining or \
                game.state.seconds_remaining <= 0:
            update_state_display()

    def game_controller_send(self, message):
        if message[:6] == 'STATE:' or message[:6] == 'SCORE:' or message == 'DROPPEDBALL':
            # we don't want to send twice the same STATE or SCORE message
            if self.game_controller_send.sent_once == message:
                return False
            self.game_controller_send.sent_once = message
            if message[6:] in ['READY', 'SET']:
                game.wait_for_state = message[6:]
            elif message[6:] == 'PLAY':
                game.wait_for_state = 'PLAYING'
            elif (message[:6] == 'SCORE:' or
                  message == 'DROPPEDBALL'):
                game.wait_for_state = 'FINISHED' if game.penalty_shootout else 'READY'
            elif message[6:] == "PENALTY-SHOOTOUT":
                game.wait_for_state = 'INITIAL'
        if ':' in message:
            msg_start = message.split(':', 1)[0]
            if msg_start in GAME_INTERRUPTIONS:
                if 'ABORT' in message or 'EXECUTE' in message:
                    game.wait_for_sec_state = 'NORMAL'
                    game.wait_for_sec_phase = 0
                else:
                    game.wait_for_sec_state = msg_start
                    if 'READY' in message:
                        game.wait_for_sec_phase = 1
                    elif 'PREPARE' in message:
                        game.wait_for_sec_phase = 2
                    else:
                        game.wait_for_sec_phase = 0
                info(f"Waiting for secondary state: {game.wait_for_sec_state}:{game.wait_for_sec_phase}")
        self.game_controller_send_id += 1
        if message[:6] != 'CLOCK:':
            info(f'Sending {self.game_controller_send_id}:{message} to GameController.')
        message = f'{self.game_controller_send_id}:{message}\n'
        game.controller.sendall(message.encode('ascii'))
        # info(f'sending {message.strip()} to GameController')
        self.game_controller_send_unanswered[self.game_controller_send_id] = message.strip()
        answered = False
        sent_id = self.game_controller_send_id
        while True:
            try:
                answers = game.controller.recv(1024).decode('ascii').split('\n')
                for answer in answers:
                    if answer == '':
                        continue
                    try:
                        id, result = answer.split(':')
                        if int(id) == sent_id:
                            answered = True
                    except ValueError:
                        error(f'Cannot split {answer}')
                        self.clean_exit()
                    try:
                        answered_message = self.game_controller_send_unanswered[int(id)]
                        del self.game_controller_send_unanswered[int(id)]
                    except KeyError:
                        error(f'Received acknowledgment message for unknown message: {id}')
                        self.clean_exit()
                    if result == 'OK':
                        continue
                    if result == 'INVALID':
                        error(f'Received invalid answer from GameController for message {answered_message}.')
                        self.clean_exit()
                    elif result == 'ILLEGAL':
                        info_msg = f"Received illegal answer from GameController for message {answered_message}."
                        if "YELLOW" in message:
                            warning(info_msg)
                        else:
                            error(info_msg)
                            self.clean_exit()
                    else:
                        error(f'Received unknown answer from GameController: {answer}.')
                        self.clean_exit()
            except BlockingIOError:
                if answered or ':CLOCK:' in message:
                    break
                else:  # keep sending CLOCK messages to keep the GameController happy
                    info(f'Waiting for GameController to answer to {message.strip()}.')
                    time.sleep(0.2)
                    self.game_controller_send_id += 1
                    clock_message = f'{self.game_controller_send_id}:CLOCK:{time_count}\n'
                    game.controller.sendall(clock_message.encode('ascii'))
                    self.game_controller_send_unanswered[self.game_controller_send_id] = clock_message.strip()
        # We are waiting for a specific update from the GC before testing anything else
        while game.wait_for_state is not None or game.wait_for_sec_state is not None or game.wait_for_sec_phase is not None:
            self.game_controller_receive()

        return True

    def append_solid(self, solid, solids, tagged_solids, active_tag=None):  # we list only the hands and feet
        name_field = solid.getField('name')
        if name_field:
            name = name_field.getSFString()
            tag_start = name.rfind('[')
            tag_end = name.rfind(']')
            if tag_start != -1 and tag_end != -1:
                active_tag = name[tag_start+1:tag_end]
            if name.endswith("[hand]") or name.endswith("[foot]"):
                solids.append(solid)
            if active_tag is not None:
                tagged_solids[name] = active_tag
        children = solid.getProtoField('children') if solid.isProto() else solid.getField('children')
        for i in range(children.getCount()):
            child = children.getMFNode(i)
            if child.getType() in [Node.ROBOT, Node.SOLID, Node.GROUP, Node.TRANSFORM, Node.ACCELEROMETER, Node.CAMERA, Node.GYRO,
                                   Node.TOUCH_SENSOR]:
                self.append_solid(child, solids, tagged_solids, active_tag)
                continue
            if child.getType() in [Node.HINGE_JOINT, Node.HINGE_2_JOINT, Node.SLIDER_JOINT, Node.BALL_JOINT]:
                endPoint = child.getProtoField('endPoint') if child.isProto() else child.getField('endPoint')
                solid = endPoint.getSFNode()
                if solid.getType() == Node.NO_NODE or solid.getType() == Node.SOLID_REFERENCE:
                    continue
                self.append_solid(solid, solids, tagged_solids, None)  # active tag is reset after a joint

    def list_player_solids(self, player, color, number):
        robot = player['robot']
        player['solids'] = []
        player['tagged_solids'] = {}  # Keys: name of solid, Values: name of tag
        solids = player['solids']
        self.append_solid(robot, solids, player['tagged_solids'])
        if len(solids) != 4:
            info(f"Tagged solids: {player['tagged_solids']}")
            error(f'{color} player {number}: invalid number of [hand]+[foot], received {len(solids)}, expected 4.')
            self.clean_exit()

    def list_team_solids(self, team):
        for number in team['players']:
            self.list_player_solids(team['players'][number], team['color'], number)

    def list_solids(self):
        self.list_team_solids(red_team)
        self.list_team_solids(blue_team)

    def show_polygon(self, vertices):
        polygon = self.supervisor.getFromDef('POLYGON')
        if polygon:
            polygon.remove()
        material = 'Material { diffuseColor 1 1 0 }'
        appearance = f'Appearance {{ material {material} }}'
        point = 'point ['
        for vertex in vertices:
            point += ' ' + str(vertex[0]) + ' ' + str(vertex[1]) + f' {game.field.turf_depth + 0.001},'  # 1 mm above turf
        point = point[:-1]
        point += ' ]'
        coord = f'Coordinate {{ {point} }}'
        coordIndex = '['
        for i in range(len(vertices)):
            coordIndex += ' ' + str(i)
        coordIndex += ' -1 ]'
        geometry = f'IndexedFaceSet {{ coord {coord} coordIndex {coordIndex} }}'
        shape = f'DEF POLYGON Shape {{ appearance {appearance} geometry {geometry} castShadows FALSE isPickable FALSE }}'
        children = self.supervisor.getRoot().getField('children')
        children.importMFNodeFromString(-1, shape)

    def update_team_ball_holding(self, team):
        players_close_to_the_ball = []
        numbers = []
        goalkeeper_number = None
        for number in team['players']:
            player = team['players'][number]
            d = distance2(player['position'], game.ball_position)
            if d <= game.field.ball_vincity:
                if self.is_goalkeeper(team, number):
                    goalkeeper_number = number
                players_close_to_the_ball.append(player)
                numbers.append(number)

        goalkeeper_hold_ball = False
        if goalkeeper_number is not None:  # goalkeeper is in vincity of ball
            goalkeeper = team['players'][goalkeeper_number]
            points = np.empty([4, 2])
            aabb = None
            i = 0
            for solid in goalkeeper['solids']:
                position = solid.getPosition()
                aabb = update_aabb(aabb, position)
                points[i] = [position[0], position[1]]
                i += 1
            # check for collision between AABB of goalkeeper and ball
            if aabb_circle_collision(aabb, game.ball_position[0], game.ball_position[1], game.ball_radius * self.config.BALL_HOLDING_RATIO):
                hull = ConvexHull(points)
                hull_vertices = np.take(points, hull.vertices, 0)
                goalkeeper_hold_ball = polygon_circle_collision(hull_vertices, game.ball_position,
                                                                game.ball_radius * self.config.BALL_HOLDING_RATIO)

        n = len(players_close_to_the_ball)
        hold_ball = False
        if n > 0:
            aabb = None
            points = np.empty([4 * n, 2])
            i = 0
            for player in players_close_to_the_ball:
                for solid in player['solids']:
                    position = solid.getPosition()
                    aabb = update_aabb(aabb, position)
                    points[i] = [position[0], position[1]]
                    i += 1
            # check for collision between AABB of players and ball
            if aabb_circle_collision(aabb, game.ball_position[0], game.ball_position[1], game.ball_radius * self.config.BALL_HOLDING_RATIO):
                hull = ConvexHull(points)
                hull_vertices = np.take(points, hull.vertices, 0)
                hold_ball = polygon_circle_collision(hull_vertices, game.ball_position, game.ball_radius * self.config.BALL_HOLDING_RATIO)
        players_holding_time_window = team['players_holding_time_window']
        index = int(time_count / time_step) % len(players_holding_time_window)
        players_holding_time_window[index] = hold_ball

        goalkeeper_holding_time_window = team['goalkeeper_holding_time_window']
        index = int(time_count / time_step) % len(goalkeeper_holding_time_window)
        goalkeeper_holding_time_window[index] = goalkeeper_hold_ball

        color = team['color']
        if 'hold_ball' in team:
            if not hold_ball:
                delay = int((time_count - team['hold_ball']) / 100) / 10
                info(f'{color.capitalize()} team released the ball after {delay} seconds.')
                del team['hold_ball']
        elif hold_ball:
            team['hold_ball'] = time_count
            info(f'{color.capitalize()} team ({numbers}) is holding the ball.')

        if 'goalkeeper_hold_ball' in team:
            if not goalkeeper_hold_ball:
                delay = int((time_count - team['goalkeeper_hold_ball']) / 100) / 10
                info(f'{color.capitalize()} goalkeeper released the ball after {delay} seconds.')
                del team['goalkeeper_hold_ball']
        elif goalkeeper_hold_ball:
            team['goalkeeper_hold_ball'] = time_count
            info(f'{color.capitalize()} goalkeeper is holding the ball.')

    def update_ball_holding(self):
        self.update_team_ball_holding(red_team)
        self.update_team_ball_holding(blue_team)

    def init_team(self, team):
        # check validity of team files
        # the players IDs should be "1", "2", "3", "4" for four players, "1", "2", "3" for three players, etc.
        count = 1
        for number in team['players']:
            count += 1
            player = team['players'][number]
            player['outside_circle'] = True
            player['outside_field'] = True
            player['inside_field'] = False
            player['on_outer_line'] = False
            player['inside_own_side'] = False
            player['outside_goal_area'] = True
            player['outside_penalty_area'] = True
            player['left_turf_time'] = None
            # Stores tuples of with (time_count[int], dic) at a 1Hz frequency
            player['history'] = []
            window_size = int(1000 / time_step)  # one second window size
            player['velocity_buffer'] = [[0] * 6] * window_size
            player['ball_handling_start'] = None
            player['ball_handling_last'] = None

    def update_team_contacts(self, team):
        early_game_interruption = self.is_early_game_interruption()
        color = team['color']
        for number in team['players']:
            player = team['players'][number]
            robot = player['robot']
            if robot is None:
                continue
            l1 = len(player['velocity_buffer'])     # number of iterations
            l2 = len(player['velocity_buffer'][0])  # should be 6 (velocity vector size)
            player['velocity_buffer'][int(time_count / time_step) % l1] = robot.getVelocity()
            sum = [0] * l2
            for v in player['velocity_buffer']:
                for i in range(l2):
                    sum[i] += v[i]
            player['velocity'] = [s / l1 for s in sum]
            n = robot.getNumberOfContactPoints(True)
            player['contact_points'] = []
            if n == 0:  # robot is asleep
                player['asleep'] = True
                continue
            player['asleep'] = False
            player['position'] = robot.getCenterOfMass()
            # if less then 3 contact points, the contacts do not include contacts with the ground, so don't update the following
            # value based on ground collisions
            if n >= 3:
                player['outside_circle'] = True        # true if fully outside the center cicle
                player['outside_field'] = True         # true if fully outside the field
                player['inside_field'] = True          # true if fully inside the field
                player['on_outer_line'] = False        # true if robot is partially on the line surrounding the field
                player['inside_own_side'] = True       # true if fully inside its own side (half field side)
                player['outside_goal_area'] = True     # true if fully outside of any goal area
                player['outside_penalty_area'] = True  # true if fully outside of any penalty area
                outside_turf = True                    # true if fully outside turf
                fallen = False
            else:
                outside_turf = False
                fallen = True
            for i in range(n):
                point = robot.getContactPoint(i)
                node = robot.getContactPointNode(i)
                if not node:
                    continue
                name_field = node.getField('name')
                member = 'unknown body part'
                if name_field:
                    name = name_field.getSFString()
                    if name in player['tagged_solids']:
                        member = player['tagged_solids'][name]
                if point[2] > game.field.turf_depth:  # not a contact with the ground
                    if not early_game_interruption and point in game.ball.contact_points:  # ball contact
                        if member in ['arm', 'hand']:
                            player['ball_handling_last'] = time_count
                            if player['ball_handling_start'] is None:
                                player['ball_handling_start'] = time_count
                                info(f'Ball touched the {member} of {color} player {number}.')
                            if (game.throw_in and
                                    game.ball_position[2] > game.field.turf_depth + game.ball_radius + BALL_LIFT_THRESHOLD):
                                game.throw_in_ball_was_lifted = True
                        else:  # the ball was touched by another part of the robot
                            game.throw_in = False  # if the ball was hit by any player, we consider the throw-in (if any) complete
                        if game.ball_first_touch_time == 0:
                            game.ball_first_touch_time = time_count
                        game.ball_last_touch_time = time_count
                        if game.penalty_shootout_count >= 10:  # extended penalty shootout
                            game.penalty_shootout_time_to_touch_ball[game.penalty_shootout_count - 10] = \
                                60 - game.state.seconds_remaining
                        if game.ball_last_touch_team != color or game.ball_last_touch_player_number != int(number):
                            self.set_ball_touched(color, int(number))
                            game.ball_last_touch_time_for_display = time_count
                            action = 'kicked' if game.kicking_player_number is None else 'touched'
                            info(f'Ball {action} by {color} player {number}.')
                            if game.kicking_player_number is None:
                                game.kicking_player_number = int(number)
                        elif time_count - game.ball_last_touch_time_for_display >= 1000:  # dont produce too many touched messages
                            game.ball_last_touch_time_for_display = time_count
                            info(f'Ball touched again by {color} player {number}.')
                        step = game.state.secondary_state_info[1]
                        if step != 0 and game.state.secondary_state[6:] in GAME_INTERRUPTIONS:
                            self.game_interruption_touched(team, number)
                        continue
                    # the robot touched something else than the ball or the ground
                    player['contact_points'].append(point)  # this list will be checked later for robot-robot collisions
                    continue
                if distance2(point, [0, 0]) < game.field.circle_radius:
                    player['outside_circle'] = False
                if game.field.point_inside(point, include_turf=True):
                    outside_turf = False
                if game.field.point_inside(point):
                    player['outside_field'] = False
                    if abs(point[0]) > game.field.size_x - game.field.penalty_area_length and \
                            abs(point[1]) < game.field.penalty_area_width / 2:
                        player['outside_penalty_area'] = False
                        if abs(point[0]) > game.field.size_x - game.field.goal_area_length and \
                                abs(point[1]) < game.field.goal_area_width / 2:
                            player['outside_goal_area'] = False
                    if not game.field.point_inside(point, include_turf=False, include_border_line=False):
                        player['on_outer_line'] = True
                else:
                    player['inside_field'] = False
                if game.side_left == (game.red.id if color == 'red' else game.blue.id):
                    if point[0] > -game.field.line_half_width:
                        player['inside_own_side'] = False
                else:
                    if point[0] < game.field.line_half_width:
                        player['inside_own_side'] = False
                # check if the robot has fallen
                if member == 'foot':
                    continue
                fallen = True
                if 'fallen' in player:  # was already down
                    continue
                info(f'{color.capitalize()} player {number} has fallen down.')
                player['fallen'] = time_count
            if not player['on_outer_line']:
                player['on_outer_line'] = not (player['inside_field'] or player['outside_field'])
            if not fallen and 'fallen' in player:  # the robot has recovered
                delay = (int((time_count - player['fallen']) / 100)) / 10
                info(f'{color.capitalize()} player {number} just recovered after {delay} seconds.')
                del player['fallen']
            if outside_turf:
                if player['left_turf_time'] is None:
                    player['left_turf_time'] = time_count
            else:
                player['left_turf_time'] = None

    def update_ball_contacts(self):
        game.ball.contact_points = []
        for i in range(game.ball.getNumberOfContactPoints()):
            point = game.ball.getContactPoint(i)
            if point[2] <= game.field.turf_depth:  # contact with the ground
                continue
            game.ball.contact_points.append(point)
            break

    def update_contacts(self):
        """Only updates the contact of objects which are not asleep"""
        self.update_ball_contacts()
        self.update_team_contacts(red_team)
        self.update_team_contacts(blue_team)

    def find_robot_contact(self, team, point):
        for number in team['players']:
            if point in team['players'][number]['contact_points']:
                return number
        return None

    def update_team_robot_contacts(self, team):
        for number in team['players']:
            player = team['players'][number]
            contact_points = player['contact_points']
            if len(contact_points) == 0:
                continue
            opponent_team = red_team if team == blue_team else blue_team
            opponent_number = None
            for point in contact_points:
                opponent_number = self.find_robot_contact(opponent_team, point)
                if opponent_number is not None:
                    if team == red_team:
                        red_number = number
                        blue_number = opponent_number
                    else:
                        red_number = opponent_number
                        blue_number = number
                    fcm = game.forceful_contact_matrix
                    if (not fcm.contact(red_number, blue_number, time_count - time_step) and
                            not fcm.contact(red_number, blue_number, time_count)):
                        info(f'{time_count}: contact between {team["color"]} player {number} and '
                             f'{opponent_team["color"]} player {opponent_number}.')
                    fcm.set_contact(red_number, blue_number, time_count)

    def update_robot_contacts(self):
        game.forceful_contact_matrix.clear(time_count)
        self.update_team_robot_contacts(red_team)
        self.update_team_robot_contacts(blue_team)

    def update_histories(self):
        for team in [red_team, blue_team]:
            for number in team['players']:
                player = team['players'][number]
                # Remove old ball_distances
                if len(player['history']) > 0 \
                        and (time_count - player['history'][0][0]) > self.config.INACTIVE_GOALKEEPER_TIMEOUT * 1000:
                    player['history'].pop(0)
                # If enough time has elapsed, add an entry
                if len(player['history']) == 0 or (time_count - player['history'][-1][0]) > self.config.BALL_DIST_PERIOD * 1000:
                    ball_dist = distance2(player['position'], game.ball_position)
                    own_goal_area = player['inside_own_side'] and not player['outside_goal_area']
                    entry = (time_count, {"ball_distance": ball_dist, "own_goal_area": own_goal_area})
                    player['history'].append(entry)

    def update_team_penalized(self, team):
        color = team['color']
        index = self.team_index(color)
        for number in team['players']:
            player = team['players'][number]
            if player['robot'] is None:
                continue
            p = game.state.teams[index].players[int(number) - 1]
            if p.number_of_red_cards > 0:
                # sending red card robot far away from the field
                t = copy.deepcopy(player['reentryStartingPose']['translation'])
                t[0] = 50
                t[1] = (10 + int(number)) * (1 if color == 'red' else -1)
                self.reset_player(color, number, 'reentryStartingPose', t)
                customData = player['robot'].getField('customData')
                customData.setSFString('red_card')  # disable all devices of the robot
                player['penalized'] = 'red_card'
                # FIXME: unfortunately, player['robot'].remove() crashes webots
                # Once this is fixed, we should remove the robot, which seems to be a better solution
                # than moving it away from the field
                player['robot'] = None
                info(f'Sending {color} player {number} to {t}. (team_index: {index})')
                if 'stabilize' in player:
                    del player['stabilize']
                player['outside_field'] = True
            elif 'enable_actuators_at' in player:
                timing_ok = time_count >= player['enable_actuators_at']
                penalty_ok = 'penalized' not in player or p.penalty == 0
                if timing_ok and penalty_ok:
                    customData = player['robot'].getField('customData')
                    info(f'Enabling actuators of {color} player {number}.')
                    customData.setSFString('')
                    del player['enable_actuators_at']
                    if 'penalized' in player:
                        del player['penalized']

    def update_penalized(self):
        self.update_team_penalized(red_team)
        self.update_team_penalized(blue_team)

    def already_penalized(self, player):
        return 'penalized' in player

    def send_penalty(self, player, penalty, reason, log=None):
        if 'yellow_card' not in player and self.already_penalized(player):
            return
        player['penalty'] = penalty
        player['penalty_reason'] = reason
        if log is not None:
            info(log)

    def forceful_contact_foul(self, team, number, opponent_team, opponent_number, distance_to_ball, message):
        player = team['players'][number]
        if player['outside_penalty_area']:
            area = 'outside penalty area'
        else:
            area = 'inside penalty area'
        info(f'{team["color"].capitalize()} player {number} committed a forceful contact foul on '
             f'{opponent_team["color"]} player {opponent_number} ({message}) {area}.')
        game.forceful_contact_matrix.clear_all()
        opponent = opponent_team['players'][opponent_number]
        immunity_timeout = time_count + self.config.FOUL_PENALTY_IMMUNITY * 1000
        opponent['penalty_immunity'] = immunity_timeout
        player['penalty_immunity'] = immunity_timeout
        freekick_team_id = game.blue.id if team['color'] == "red" else game.red.id
        foul_far_from_ball = distance_to_ball > self.config.FOUL_BALL_DISTANCE
        if game.penalty_shootout and self.is_penalty_kicker(team, number):
            info(f'Kicker {team["color"]} {number} performed forceful contact during penaltykick -> end of trial')
            self.next_penalty_shootout()
        info(f"Ball in play: {game.in_play}, foul far from ball: {foul_far_from_ball}")
        if foul_far_from_ball or not game.in_play or game.penalty_shootout:
            self.send_penalty(player, 'PHYSICAL_CONTACT', 'forceful contact foul')
        else:
            offence_location = team['players'][number]['position']
            self.interruption('FREEKICK', freekick_team_id, offence_location)

    def goalkeeper_inside_own_goal_area(self, team, number):
        if self.is_goalkeeper(team, number):
            goalkeeper = team['players'][number]
            if not goalkeeper['outside_goal_area'] and goalkeeper['inside_own_side']:
                return True
        return False

    def moves_to_ball(self, player, velocity, velocity_squared):
        if velocity_squared < self.config.FOUL_SPEED_THRESHOLD * self.config.FOUL_SPEED_THRESHOLD:
            return True
        rx = game.ball_position[0] - player['position'][0]
        ry = game.ball_position[1] - player['position'][1]
        vx = velocity[0]
        vy = velocity[1]
        angle = math.acos((rx * vx + ry * vy) / (math.sqrt(rx * rx + ry * ry) * math.sqrt(vx * vx + vy * vy)))
        return angle < self.config.FOUL_DIRECTION_THRESHOLD

    def readable_number_list(self, number_list, width=5, nb_digits=2):
        fmt = f"%{width}.{nb_digits}f"
        return f"[{' '.join([fmt % elem for elem in number_list])}]"

    def check_team_forceful_contacts(self, team, number, opponent_team, opponent_number):
        p1 = team['players'][number]
        if 'penalty_immunity' in p1:
            if p1['penalty_immunity'] < time_count:
                del p1['penalty_immunity']
            else:
                return
        p2 = opponent_team['players'][opponent_number]
        d1 = distance2(p1['position'], game.ball_position)
        d2 = distance2(p2['position'], game.ball_position)
        p1_str = f"{team['color']} {number}"
        p2_str = f"{opponent_team['color']} {opponent_number}"
        debug_messages = [f"Check if {p1_str} is performing a foul on {p2_str}",
                          f"{p1_str:6s}: at {self.readable_number_list(p1['position'])}, dist to ball: {d1:.2f}",
                          f"{p2_str:6s}: at {self.readable_number_list(p2['position'])}, dist to ball: {d2:.2f}"]
        if self.goalkeeper_inside_own_goal_area(opponent_team, opponent_number):
            info(debug_messages)
            self.forceful_contact_foul(team, number, opponent_team, opponent_number, d1, 'goalkeeper')
            return True
        if team == red_team:
            red_number = number
            blue_number = opponent_number
        else:
            red_number = opponent_number
            blue_number = number
        if game.forceful_contact_matrix.long_collision(red_number, blue_number):
            if d1 < self.config.FOUL_VINCITY_DISTANCE and d1 - d2 > self.config.FOUL_DISTANCE_THRESHOLD:
                collision_time = game.forceful_contact_matrix.get_collision_time(red_number, blue_number)
                debug_messages.append(f"Pushing time: {collision_time} > {self.config.FOUL_PUSHING_TIME} over the last {self.config.FOUL_PUSHING_PERIOD}")
                debug_messages.append(f"Difference of distance: {d1-d2} > {self.config.FOUL_DISTANCE_THRESHOLD}")
                info(debug_messages)
                self.forceful_contact_foul(team, number, opponent_team, opponent_number, d1, 'long_collision')
                return True
        v1 = p1['velocity']
        v2 = p2['velocity']
        v1_squared = v1[0] * v1[0] + v1[1] * v1[1]
        v2_squared = v2[0] * v2[0] + v2[1] * v2[1]
        if not v1_squared > self.config.FOUL_SPEED_THRESHOLD * self.config.FOUL_SPEED_THRESHOLD:
            return False
        debug_messages.append(f"{p1_str:6s}: velocity: {self.readable_number_list(v1[:3])}, speed: {math.sqrt(v1_squared):.2f}")
        debug_messages.append(f"{p2_str:6s}: velocity: {self.readable_number_list(v2[:3])}, speed: {math.sqrt(v2_squared):.2f}")
        if d1 < self.config.FOUL_VINCITY_DISTANCE:
            debug_messages.append(f"{p1_str} is close to the ball ({d1:.2f} < {self.config.FOUL_VINCITY_DISTANCE})")
            if self.moves_to_ball(p2, v2, v2_squared):
                if not self.moves_to_ball(p1, v1, v1_squared):
                    info(debug_messages)
                    self.forceful_contact_foul(team, number, opponent_team, opponent_number, d1,
                                               'opponent moving towards the ball, charge')
                    return True
                if d1 - d2 > self.config.FOUL_DISTANCE_THRESHOLD:
                    debug_messages.append(f"{p2_str} is significantly closer to the ball than {p1_str}: "
                                          f"({d1-d2:.2f} < {self.config.FOUL_DISTANCE_THRESHOLD})")
                    info(debug_messages)
                    self.forceful_contact_foul(team, number, opponent_team, opponent_number, d1,
                                               'opponent moving towards the ball, charge from behind')
                    return True
        elif math.sqrt(v1_squared) - math.sqrt(v2_squared) > self.config.FOUL_SPEED_THRESHOLD:
            info(debug_messages)
            self.forceful_contact_foul(team, number, opponent_team, opponent_number, d1, 'violent collision: '
                                                                                          f'{math.sqrt(v1_squared)} - {math.sqrt(v2_squared)} > {self.config.FOUL_SPEED_THRESHOLD}')
            return True
        return False

    def check_forceful_contacts(self):
        self.update_robot_contacts()
        fcm = game.forceful_contact_matrix
        for red_number in red_team['players']:
            for blue_number in blue_team['players']:
                if not fcm.contact(red_number, blue_number, time_count):
                    continue  # no contact
                if self.check_team_forceful_contacts(red_team, red_number, blue_team, blue_number):
                    continue
                if self.check_team_forceful_contacts(blue_team, blue_number, red_team, red_number):
                    continue

    def check_team_ball_holding(self, team):
        color = team['color']
        players_holding_time_window = team['players_holding_time_window']
        size = len(players_holding_time_window)
        sum = 0
        for i in range(size):
            if players_holding_time_window[i]:
                sum += 1
        if sum > size / 2:
            info(f'{color.capitalize()} team has held the ball for too long.')
            return True
        return False

    def check_ball_holding(self):  # return the team id which gets a free kick in case of ball holding from the other team
        if self.check_team_ball_holding(red_team):
            return game.blue.id
        if self.check_team_ball_holding(blue_team):
            return game.red.id
        return None

    def reset_ball_handling(self, player):
        player['ball_handling_start'] = None
        player['ball_handling_last'] = None

    def check_team_ball_handling(self, team):
        for number in team['players']:
            player = team['players'][number]
            if player['ball_handling_start'] is None:  # ball is not handled
                continue
            duration = (player['ball_handling_last'] - player['ball_handling_start']) / 1000
            color = team['color']
            if time_count - player['ball_handling_last'] >= 1000:  # ball was released one second ago or more
                self.reset_ball_handling(player)
                if game.throw_in:
                    was_throw_in = game.throw_in
                    game.throw_in = False
                    if was_throw_in and not game.throw_in_ball_was_lifted:
                        sentence = 'throw-in with the hand or arm while the ball was not lifted by at least ' + \
                                   f'{self.config.BALL_LIFT_THRESHOLD * 100} cm'
                        self.send_penalty(player, 'BALL_MANIPULATION', sentence, f'{color.capitalize()} player {number} {sentence}.')
                        continue
            goalkeeper = self.goalkeeper_inside_own_goal_area(team, number)
            if not goalkeeper and not game.throw_in:
                self.reset_ball_handling(player)
                sentence = 'touched the ball with its hand or arm'
                if game.penalty_shootout and self.is_penalty_kicker(team, number):
                    info("Kicker {color.capitalize()} {number} has fallen down and not recovered -> end of trial")
                else:
                    self.send_penalty(player, 'BALL_MANIPULATION', sentence, f'{color.capitalize()} player {number} {sentence}.')
                continue
            ball_on_the_ground = game.ball_position[2] <= game.field.turf_depth + game.ball_radius
            if game.throw_in:
                if duration >= self.config.BALL_HANDLING_TIMEOUT:  # a player can handle the ball for 10 seconds for throw-in, no more
                    self.reset_ball_handling(player)
                    sentence = f'touched the ball with its hand or arm for more than {self.config.BALL_HANDLING_TIMEOUT} ' + \
                                'seconds during throw-in'
                    self.send_penalty(player, 'BALL_MANIPULATION', sentence, f'{color.capitalize()} player {number} {sentence}.')
                    continue
            # goalkeeper case
            if duration >= self.config.BALL_HANDLING_TIMEOUT:
                if (game.ball_previous_touch_team == game.ball_last_touch_team and
                        time_count - player['ball_handling_start'] >= 1000):  # ball handled by goalkeeper for 1 second or more
                    self.reset_ball_handling(player)
                    sentence = 'handled the ball after it received it from teammate' \
                        if game.ball_last_touch_player_number == int(number) else 'released the ball and retook it'
                    info(f'{color.capitalize()} goalkeeper {number} {sentence}.')
                    return True  # a freekick will be awarded
                self.reset_ball_handling(player)
                info(f'{color.capitalize()} goalkeeper {number} handled the ball up for more than '
                     f'{self.config.BALL_HANDLING_TIMEOUT} seconds.')
                return True  # a freekick will be awarded
            if ball_on_the_ground and duration >= self.config.GOALKEEPER_GROUND_BALL_HANDLING:
                self.reset_ball_handling(player)
                info(f'{color.capitalize()} goalkeeper {number} handled the ball on the ground for more than '
                     f'{self.config.GOALKEEPER_GROUND_BALL_HANDLING} seconds.')
                return True  # a freekick will be awarded
        return False  # not free kick awarded

    def check_ball_handling(self):  # return the team id which gets a free kick in case of wrong ball handling by a goalkeeper
        if self.check_team_ball_handling(red_team):
            return game.blue.id
        if self.check_team_ball_handling(blue_team):
            return game.red.id
        return None

    def check_team_fallen(self, team):
        color = team['color']
        penalty = False
        for number in team['players']:
            player = team['players'][number]
            if self.already_penalized(player):
                continue
            if 'fallen' in player and time_count - player['fallen'] > 1000 * self.config.FALLEN_TIMEOUT:
                del player['fallen']
                if game.penalty_shootout and self.is_penalty_kicker(team, number):
                    info("Kicker {color.capitalize()} {number} has fallen down and not recovered -> end of trial")
                    self.next_penalty_shootout()
                else:
                    self.send_penalty(player, 'INCAPABLE', 'fallen down',
                                     f'{color.capitalize()} player {number} has fallen down and not recovered in 20 seconds.')
                penalty = True
        return penalty

    def check_fallen(self):
        red = self.check_team_fallen(red_team)
        blue = self.check_team_fallen(blue_team)
        return red or blue

    def check_team_inactive_goalkeeper(self, team):
        # Since there is only one goalkeeper, we can safely return once we have a 'proof' that the goalkeeper is not inactive
        for number in team['players']:
            if not self.is_goalkeeper(team, number):
                continue
            player = team['players'][number]
            if self.already_penalized(player) or len(player['history']) == 0:
                return
            # If player was out of his own goal area recently, it can't be considered as inactive
            if not all([e[1]["own_goal_area"] for e in player['history']]):
                return
            ball_distances = [e[1]["ball_distance"] for e in player['history']]
            if max(ball_distances) > self.config.INACTIVE_GOALKEEPER_DIST:
                return
            # In order to measure progress toward the ball, we just look if one of distance measured is significantly lower
            # than what happened previously. active_dist keeps track of the threshold below which we consider the player as
            # moving toward the ball.
            active_dist = 0
            for d in ball_distances:
                if d < active_dist:
                    return
                new_active_dist = d - self.config.INACTIVE_GOALKEEPER_PROGRESS
                if new_active_dist > active_dist:
                    active_dist = new_active_dist
            info(f'Goalkeeper did not move toward the ball over the last {self.config.INACTIVE_GOALKEEPER_TIMEOUT} seconds')
            self.send_penalty(player, 'INCAPABLE', 'Inactive goalkeeper')

    def check_inactive_goalkeepers(self):
        self.check_team_inactive_goalkeeper(red_team)
        self.check_team_inactive_goalkeeper(blue_team)

    def check_team_away_from_ball(self, team, distance):
        for number in team['players']:
            player = team['players'][number]
            if self.already_penalized(player):
                continue
            d = distance2(player['position'], game.ball_position)
            if d < distance:
                color = team['color']
                self.send_penalty(player, 'INCAPABLE', f'too close to ball: {d:.2f} m., should be at least {distance:.2f} m.' +
                                 f'{color.capitalize()} player {number} is too close to the ball: ' +
                                 f'({d:.2f} m., should be at least {distance:.2f} m.)')

    def check_penalty_kick_positions(self):
        for team in [red_team, blue_team]:
            defending_team = (team['color'] == 'red') ^ (game.state.secondary_state_info[0] == game.red.id)
            has_striker = False
            for number in team['players']:
                player = team['players'][number]
                if self.already_penalized(player):
                    continue
                player_x = player['position'][0]
                ahead_of_ball = game.ball_position[0] * player_x > 0 and abs(player_x) > game.field.penalty_mark_x
                near_ball = distance2(game.ball_position, player['position']) < game.field.opponent_distance_to_ball
                if ahead_of_ball:
                    if not defending_team:
                        # In rules version from June 21st 2021, there are no constraint on the position of the striker.
                        # Here, we assume that the striker is not allowed to be in front of the ball
                        self.send_penalty(player, 'INCAPABLE', "Field player of the attacking team in front of penalty mark")
                    elif self.is_goalkeeper(team, number):
                        on_goal_line_or_behind = (player['on_outer_line'] or player['outside_field']) and \
                                                 abs(player['position'][1]) <= self.config.GOAL_WIDTH
                        if not on_goal_line_or_behind:
                            self.send_penalty(player, 'INCAPABLE', "Defending goalkeeper between goal line and penalty mark")
                    else:
                        self.send_penalty(player, 'INCAPABLE', "Field player of the defending team in front of the penalty mark")
                elif near_ball:
                    if defending_team:
                        self.send_penalty(player, 'INCAPABLE', "Player of the defending team near ball (penaltykick)")
                    elif has_striker:
                        self.send_penalty(player, 'INCAPABLE', "Player of the attacking team has already a striker")
                    else:
                        has_striker = True
                        info(f"Player {team['color']} {number} is considered as striker")

    def check_team_start_position(self, team):
        penalty = False
        for number in team['players']:
            player = team['players'][number]
            if self.already_penalized(player):
                continue
            if not player['outside_field']:
                self.send_penalty(player, 'INCAPABLE', 'halfTimeStartingPose inside field')
                penalty = True
            elif not player['inside_own_side']:
                self.send_penalty(player, 'INCAPABLE', 'halfTimeStartingPose outside team side')
                penalty = True
        return penalty

    def check_start_position(self):
        red = self.check_team_start_position(red_team)
        blue = self.check_team_start_position(blue_team)
        return red or blue

    def check_team_kickoff_position(self, team):
        color = team['color']
        team_id = game.red.id if color == 'red' else game.blue.id
        penalty = False
        for number in team['players']:
            player = team['players'][number]
            if self.already_penalized(player):
                continue
            if not player['inside_field']:
                self.send_penalty(player, 'INCAPABLE', 'outside of field at kick-off')
                penalty = True
            elif not player['inside_own_side']:
                self.send_penalty(player, 'INCAPABLE', 'outside team side at kick-off')
                penalty = True
            elif game.kickoff != team_id and not player['outside_circle']:
                self.send_penalty(player, 'INCAPABLE', 'inside center circle during opponent\'s kick-off')
                penalty = True
        return penalty

    def check_kickoff_position(self):
        red = self.check_team_kickoff_position(red_team)
        blue = self.check_team_kickoff_position(blue_team)
        return red or blue

    def check_team_dropped_ball_position(self, team):
        for number in team['players']:
            player = team['players'][number]
            if self.already_penalized(player):
                continue
            if not player['outside_circle']:
                self.send_penalty(player, 'INCAPABLE', 'inside center circle during dropped ball')
            elif not player['inside_own_side']:
                self.send_penalty(player, 'INCAPABLE', 'outside team side during dropped ball')

    def check_dropped_ball_position(self):
        self.check_team_dropped_ball_position(red_team)
        self.check_team_dropped_ball_position(blue_team)

    def check_team_outside_turf(self, team):
        color = team['color']
        for number in team['players']:
            player = team['players'][number]
            if self.already_penalized(player):
                continue
            if player['left_turf_time'] is None:
                continue
            if time_count - player['left_turf_time'] < self.config.OUTSIDE_TURF_TIMEOUT * 1000:
                continue
            if game.penalty_shootout and self.is_penalty_kicker(team, number):
                info(f'Kicker {color.capitalize()} {number} left the field -> end of trial')
                self.next_penalty_shootout()
            else:
                self.send_penalty(player, 'INCAPABLE', f'left the field for more than {self.config.OUTSIDE_TURF_TIMEOUT} seconds',
                                 f'{color.capitalize()} player {number} left the field for more than {self.config.OUTSIDE_TURF_TIMEOUT} seconds.')

    def check_outside_turf(self):
        self.check_team_outside_turf(red_team)
        self.check_team_outside_turf(blue_team)

    def check_team_penalized_in_field(self, team):
        color = team['color']
        penalty = False
        for number in team['players']:
            player = team['players'][number]
            if 'penalized' not in player:
                continue  # skip non penalized players
            if player['penalized'] == 'red_card':
                continue  # skip red card players
            if player['outside_field']:
                continue
            player['yellow_card'] = True
            info(f'Penalized {color} player {number} re-entered the field...')
            self.send_penalty(player, 'INCAPABLE', 'penalized player re-entered field',
                              f'Penalized {color} player {number} re-entered the field: shown yellow card.')
            penalty = True
        return penalty

    def check_penalized_in_field(self):
        red = self.check_team_penalized_in_field(red_team)
        blue = self.check_team_penalized_in_field(blue_team)
        return red or blue

    def check_circle_entrance(self, team):
        penalty = False
        for number in team['players']:
            player = team['players'][number]
            if self.already_penalized(player):
                continue
            if not player['outside_circle']:
                color = team['color']
                self.send_penalty(player, 'INCAPABLE', 'entered circle during oppenent\'s kick-off',
                                  f'{color.capitalize()} player {number} entering circle during opponent\'s kick-off.')
                penalty = True
        return penalty

    def check_ball_must_kick(self, team):
        if game.ball_last_touch_team is None:
            return False  # nobody touched the ball
        if game.dropped_ball or game.ball_last_touch_team == game.ball_must_kick_team:
            return False  # no foul
        for number in team['players']:
            if not game.ball_last_touch_player_number == int(number):
                continue
            player = team['players'][number]
            if self.already_penalized(player):
                continue
            color = team['color']
            self.send_penalty(player, 'INCAPABLE', 'non-kicking player touched ball not in play',
                              f'Non-kicking {color} player {number} touched ball not in play. Ball was touched by wrong team.')
            break
        return True

    def set_ball_touched(self, team_color, player_number):
        game.ball_previous_touch_team = game.ball_last_touch_team
        game.ball_previous_touch_player_number = game.ball_last_touch_player_number
        game.ball_last_touch_team = team_color
        game.ball_last_touch_player_number = player_number
        game.dropped_ball = False

    def reset_ball_touched(self):
        game.ball_previous_touch_team = None
        game.ball_previous_touch_player_number = None
        game.ball_last_touch_team = None
        game.ball_last_touch_player_number = None

    def is_game_interruption(self):
        if not hasattr(game, "state"):
            return False
        return game.state.secondary_state[6:] in GAME_INTERRUPTIONS

    def is_early_game_interruption(self):
        """
        Return true if the active state is a game interruption and phase is 0.

        Note: During this step, robots are allowed to commit some infringements such as touching a ball that is not in play.
        """
        return self.is_game_interruption() and game.state.secondary_state_info[1] == 0

    def game_interruption_touched(self, team, number):
        """
        Applies the associated actions for when a robot touches the ball during step 1 and 2 of game interruptions

        1. If opponent touches the ball, robot receives a warning and RETAKE is sent
        2. If team with game_interruption touched the ball, player receives warning and ABORT is sent
        """
        # Warnings only applies in step 1 and 2 of game interruptions
        team_id = game.red.id if team['color'] == 'red' else game.blue.id
        opponent = team_id != game.interruption_team
        if opponent:
            game.in_play = None
            game.ball_set_kick = True
            game.interruption_countdown = self.config.SIMULATED_TIME_INTERRUPTION_PHASE_0
            info(f"Ball touched by opponent, retaking {GAME_INTERRUPTIONS[game.interruption]}")
            info(f"Reset interruption_countdown to {game.interruption_countdown}")
            self.game_controller_send(f'{game.interruption}:{game.interruption_team}:RETAKE')
        else:
            game.in_play = time_count
            info(f"Ball touched before execute, aborting {GAME_INTERRUPTIONS[game.interruption]}")
            self.game_controller_send(f'{game.interruption}:{game.interruption_team}:ABORT')
        self.game_controller_send(f'CARD:{team_id}:{number}:WARN')

    def get_first_available_spot(self, team_color, number, reentry_pos):
        """Return the first available spot to enter on one side of the field given the reentry_pos"""
        if not self.is_other_robot_near(team_color, number, reentry_pos, game.field.robot_radius):
            return reentry_pos
        preferred_dir = 1 if reentry_pos[1] > game.ball_position[1] else -1
        max_iterations = math.ceil(reentry_pos[1] / game.field.penalty_offset)
        basic_offset = np.array([game.field.penalty_offset, 0, 0])
        initial_pos = np.array(reentry_pos)
        for i in range(1, max_iterations):
            for direction in [preferred_dir, -preferred_dir]:
                current_pos = initial_pos + direction * i * basic_offset
                opposite_sides = current_pos[0] * initial_pos[0] < 0  # current_pos should be on the other side
                out_of_field = abs(current_pos[0]) > game.field.size_x
                if opposite_sides or out_of_field:
                    continue
                if not self.is_other_robot_near(team_color, number, current_pos, game.field.robot_radius):
                    return current_pos.tolist()
        return None

    def place_player_at_penalty(self, player, team, number):
        color = team['color']
        t = copy.deepcopy(player['reentryStartingPose']['translation'])
        r = copy.deepcopy(player['reentryStartingPose']['rotation'])
        t[0] = game.field.penalty_mark_x if t[0] > 0 else -game.field.penalty_mark_x
        if (game.ball_position[1] > 0 and t[1] > 0) or (game.ball_position[1] < 0 and t[1] < 0):
            t[1] = -t[1]
            r = rotate_along_z(r)
        # check if position is already occupied by a penalized robot
        info(f"placing player {color} {number} at {t}")
        pos = self.get_first_available_spot(color, number, t)
        info(f"-> pos: {pos}")
        if pos is None:
            t[1] = -t[1]
            r = rotate_along_z(r)
            pos = self.get_first_available_spot(color, number, t)
            if pos is None:
                raise RuntimeError("No spot available, this should not be possible")
        self.reset_player(color, number, None, pos, r)

    def send_team_penalties(self, team):
        color = team['color']
        for number in team['players']:
            player = team['players'][number]
            if 'yellow_card' in player:
                self.game_controller_send(f'CARD:{game.red.id if color == "red" else game.blue.id}:{number}:YELLOW')
                del player['yellow_card']
            if 'penalty' in player:
                penalty = player['penalty']
                reason = player['penalty_reason']
                del player['penalty']
                del player['penalty_reason']
                player['penalty_immunity'] = time_count + self.config.FOUL_PENALTY_IMMUNITY * 1000
                team_id = game.red.id if color == 'red' else game.blue.id
                self.game_controller_send(f'PENALTY:{team_id}:{number}:{penalty}')
                self.place_player_at_penalty(player, team, number)
                player['penalized'] = self.config.REMOVAL_PENALTY_TIMEOUT
                # Once removed from the field, the robot will be in the air, therefore its status will not be updated.
                # Thus, we need to make sure it will not be considered in the air while falling
                player['outside_field'] = True
                info(f'{penalty} penalty for {color} player {number}: {reason}.')

    def send_penalties(self):
        self.send_team_penalties(red_team)
        self.send_team_penalties(blue_team)

    def stabilize_team_robots(self, team):
        color = team['color']
        for number in team['players']:
            player = team['players'][number]
            robot = player['robot']
            if robot is None:
                continue
            if 'stabilize' in player:
                if player['stabilize'] == 0:
                    info(f'Stabilizing {color} player {number}')
                    robot.resetPhysics()
                    robot.getField('translation').setSFVec3f(player['stabilize_translation'])
                    robot.getField('rotation').setSFRotation(player['stabilize_rotation'])
                    del player['stabilize']
                else:
                    player['stabilize'] -= 1

    def stabilize_robots(self):
        self.stabilize_team_robots(red_team)
        self.stabilize_team_robots(blue_team)

    def flip_pose(self, pose):
        pose['translation'][0] = -pose['translation'][0]
        pose['rotation'][3] = math.pi - pose['rotation'][3]

    def flip_poses(self, player):
        self.flip_pose(player['halfTimeStartingPose'])
        self.flip_pose(player['reentryStartingPose'])
        self.flip_pose(player['shootoutStartingPose'])
        self.flip_pose(player['goalKeeperStartingPose'])

    def flip_sides(self):  # flip sides (no need to notify GameController, it does it automatically)
        game.side_left = game.red.id if game.side_left == game.blue.id else game.blue.id
        for team in [red_team, blue_team]:
            for number in team['players']:
                self.flip_poses(team['players'][number])
        self.update_team_display()

    def reset_player(self, color, number, pose, custom_t=None, custom_r=None):
        team = red_team if color == 'red' else blue_team
        player = team['players'][number]
        robot = player['robot']
        if robot is None:
            return
        robot.loadState('__init__')
        self.list_player_solids(player, color, number)
        translation = robot.getField('translation')
        rotation = robot.getField('rotation')
        t = custom_t if custom_t else player[pose]['translation']
        r = custom_r if custom_r else player[pose]['rotation']
        translation.setSFVec3f(t)
        rotation.setSFRotation(r)
        robot.resetPhysics()
        player['stabilize'] = 5  # stabilize after 5 simulation steps
        player['stabilize_translation'] = t
        player['stabilize_rotation'] = r
        player['position'] = t
        info(f'{color.capitalize()} player {number} reset to {pose}: ' +
             f'translation ({t[0]} {t[1]} {t[2]}), rotation ({r[0]} {r[1]} {r[2]} {r[3]}).')
        info(f'Disabling actuators of {color} player {number}.')
        robot.getField('customData').setSFString('penalized')
        player['enable_actuators_at'] = time_count + int(self.config.DISABLE_ACTUATORS_MIN_DURATION * 1000)

    def reset_teams(self, pose):
        for number in red_team['players']:
            self.reset_player('red', str(number), pose)
        for number in blue_team['players']:
            self.reset_player('blue', str(number), pose)

    def is_goalkeeper(self, team, id):
        n = game.state.teams[0].team_number
        index = 0 if (n == game.red.id and team == red_team) or (n == game.blue.id and team == blue_team) else 1
        return game.state.teams[index].players[int(id) - 1].goalkeeper

    def get_penalty_attacking_team(self):
        first_team = game.penalty_shootout_count % 2 == 0
        if first_team == (game.kickoff == game.red.id):
            return red_team
        return blue_team

    def get_penalty_defending_team(self):
        first_team = game.penalty_shootout_count % 2 == 0
        if first_team == (game.kickoff != game.red.id):
            return red_team
        return blue_team

    def player_has_red_card(self, player):
        return 'penalized' in player and player['penalized'] == 'red_card'

    def is_penalty_kicker(self, team, id):
        for number in team['players']:
            if self.player_has_red_card(team['players'][number]):
                continue
            return id == number

    def penalty_kicker_player(self):
        default = game.penalty_shootout_count % 2 == 0
        attacking_team = red_team if (game.kickoff == game.blue.id) ^ default else blue_team
        for number in attacking_team['players']:
            player = attacking_team['players'][number]
            if self.player_has_red_card(player):
                continue
            return player
        return None

    def get_penalty_shootout_msg(self):
        trial = game.penalty_shootout_count + 1
        name = "penalty shoot-out"
        if game.penalty_shootout_count >= 10:
            name = f"extended {name}"
            trial -= 10
        return f"{name} {trial}/10"

    def set_penalty_positions(self):
        info(f"Setting positions for {self.get_penalty_shootout_msg()}")
        default = game.penalty_shootout_count % 2 == 0
        attacking_color = 'red' if (game.kickoff == game.blue.id) ^ default else 'blue'
        if attacking_color == 'red':
            defending_color = 'blue'
            attacking_team = red_team
            defending_team = blue_team
        else:
            defending_color = 'red'
            attacking_team = blue_team
            defending_team = red_team
        for number in attacking_team['players']:
            if self.player_has_red_card(attacking_team['players'][number]):
                continue
            if self.is_penalty_kicker(attacking_team, number):
                self.reset_player(attacking_color, number, 'shootoutStartingPose')
            else:
                self.reset_player(attacking_color, number, 'halfTimeStartingPose')
        for number in defending_team['players']:
            if self.player_has_red_card(defending_team['players'][number]):
                continue
            if self.is_goalkeeper(defending_team, number) and game.penalty_shootout_count < 10:
                self.reset_player(defending_color, number, 'goalKeeperStartingPose')
                defending_team['players'][number]['invalidGoalkeeperStart'] = None
            else:
                self.reset_player(defending_color, number, 'halfTimeStartingPose')
        x = -game.field.penalty_mark_x if (game.side_left == game.kickoff) ^ default else game.field.penalty_mark_x
        game.ball.resetPhysics()
        self.reset_ball_touched()
        game.in_play = None
        game.can_score = True
        game.can_score_own = False
        game.ball_set_kick = True
        game.ball_left_circle = True
        game.ball_must_kick_team = attacking_team['color']
        game.kicking_player_number = None
        game.ball_kick_translation[0] = x
        game.ball_kick_translation[1] = 0
        game.ball_translation.setSFVec3f(game.ball_kick_translation)

    def stop_penalty_shootout(self):
        info(f"End of {self.get_penalty_shootout_msg()}")
        if game.penalty_shootout_count == 20:  # end of extended penalty shootout
            return True
        diff = abs(game.state.teams[0].score - game.state.teams[1].score)
        if game.penalty_shootout_count == 10 and diff > 0:
            return True
        kickoff_team = game.state.teams[0] if game.kickoff == game.state.teams[0].team_number else game.state.teams[1]
        kickoff_team_leads = kickoff_team.score >= game.state.teams[0].score and kickoff_team.score >= game.state.teams[1].score
        penalty_shootout_count = game.penalty_shootout_count % 10  # supports both regular and extended shootout kicks
        if (penalty_shootout_count == 6 and diff == 3) or (penalty_shootout_count == 8 and diff == 2):
            return True  # no need to go further, score is like 3-0 after 6 shootouts or 4-2 after 8 shootouts
        if penalty_shootout_count == 7:
            if diff == 3:  # score is like 4-1
                return True
            if diff == 2 and not kickoff_team_leads:  # score is like 1-3
                return True
        elif penalty_shootout_count == 9:
            if diff == 2:  # score is like 5-3
                return True
            if diff == 1 and not kickoff_team_leads:  # score is like 3-4
                return True
        return False

    def next_penalty_shootout(self):
        game.penalty_shootout_count += 1
        if not game.penalty_shootout_goal and game.state.game_state[:8] != "FINISHED":
            info("Sending state finish to end current_penalty_shootout")
            self.game_controller_send('STATE:FINISH')
        game.penalty_shootout_goal = False
        if self.stop_penalty_shootout():
            game.over = True
            return
        if game.penalty_shootout_count == 10:
            info('Starting extended penalty shootout without a goalkeeper and goal area entrance allowed.')
        # Only prepare next penalty if team has a kicker available
        self.flip_sides()
        info(f'fliped sides: game.side_left = {game.side_left}')
        if self.penalty_kicker_player():
            self.game_controller_send('STATE:SET')
            self.set_penalty_positions()
        else:
            info("Skipping penalty trial because team has no kicker available")
            self.game_controller_send('STATE:SET')
            self.next_penalty_shootout()
        return

    def check_penalty_goal_line(self):
        """
        Checks that the goalkeepers of both teams respect the goal line rule and apply penalties if required
        """
        defending_team = self.get_penalty_defending_team()
        for number in defending_team['players']:
            player = defending_team['players'][number]
            ignore_player = self.already_penalized(player) or not self.is_goalkeeper(defending_team, number)
            if game.in_play is not None or ignore_player:
                player['invalidGoalkeeperStart'] = None
                continue
            on_goal_line_or_behind = (player['on_outer_line'] or player['outside_field']) and \
                                     abs(player['position'][1]) <= self.config.GOAL_WIDTH
            if on_goal_line_or_behind and player['inside_own_side']:
                player['invalidGoalkeeperStart'] = None
            else:
                if player['invalidGoalkeeperStart'] is None:
                    player['invalidGoalkeeperStart'] = time_count
                elif time_count - player['invalidGoalkeeperStart'] > self.config.INVALID_GOALKEEPER_TIMEOUT * 1000:
                    info(f'Goalkeeper of team {defending_team["color"]} is not on goal line since {self.config.INVALID_GOALKEEPER_TIMEOUT} sec')
                    self.send_penalty(player, 'INCAPABLE', "Not on goal line during penalty")

    def interruption(self, interruption_type, team=None, location=None, is_goalkeeper_ball_manipulation=False):
        if location is not None:
            game.ball_kick_translation[:2] = location[:2]
        if interruption_type == 'FREEKICK':
            own_side = (game.side_left == team) ^ (game.ball_position[0] < 0)
            inside_penalty_area = game.field.circle_fully_inside_penalty_area(game.ball_position, game.ball_radius)
            if inside_penalty_area and own_side:
                if is_goalkeeper_ball_manipulation:
                    # move the ball on the penalty line parallel to the goal line
                    dx = game.field.size_x - game.field.penalty_area_length
                    dy = game.field.penalty_area_width / 2
                    moved = False
                    if abs(location[0]) > dx:
                        game.ball_kick_translation[0] = dx * (-1 if location[0] < 0 else 1)
                        moved = True
                    if abs(location[1]) > dy:
                        game.ball_kick_translation[1] = dy * (-1 if location[1] < 0 else 1)
                        moved = True
                    if moved:
                        info(f'Moved the ball on the penalty line at {game.ball_kick_translation}')
                    interruption_type = 'INDIRECT_FREEKICK'
                else:
                    interruption_type = 'PENALTYKICK'
                    game.ball_kick_translation = [game.field.penalty_mark_x, 0, 0.08]
                    if location[0] < 0:
                        game.ball_kick_translation[0] *= -1
            else:
                interruption_type = 'DIRECT_FREEKICK'
            game.can_score = interruption_type != 'INDIRECT_FREEKICK'
        game.in_play = None
        game.can_score_own = False
        game.ball_set_kick = True
        game.interruption = interruption_type
        game.phase = interruption_type
        game.ball_first_touch_time = 0
        game.interruption_countdown = self.config.SIMULATED_TIME_INTERRUPTION_PHASE_0
        info(f'Interruption countdown set to {game.interruption_countdown}')
        if not team:
            game.interruption_team = game.red.id if game.ball_last_touch_team == 'blue' else game.blue.id
        else:
            game.interruption_team = team
        game.ball_must_kick_team = 'red' if game.interruption_team == game.red.id else 'blue'
        self.reset_ball_touched()
        info(f'Ball not in play, will be kicked by a player from the {game.ball_must_kick_team} team.')
        color = 'red' if game.interruption_team == game.red.id else 'blue'
        info(f'{GAME_INTERRUPTIONS[interruption_type].capitalize()} awarded to {color} team.')
        self.game_controller_send(f'{game.interruption}:{game.interruption_team}')

    def throw_in(self, left_side):
        # set the ball on the touch line for throw in
        sign = -1 if left_side else 1
        game.ball_kick_translation[0] = game.ball_exit_translation[0]
        game.ball_kick_translation[1] = sign * (game.field.size_y - game.field.line_half_width)
        game.can_score = False  # disallow direct goal
        game.throw_in = True
        game.throw_in_ball_was_lifted = False
        self.interruption('THROWIN')

    def corner_kick(self, left_side):
        # set the ball in the right corner for corner kick
        sign = -1 if left_side else 1
        game.ball_kick_translation[0] = sign * (game.field.size_x - game.field.line_half_width)
        game.ball_kick_translation[1] = game.field.size_y - game.field.line_half_width if game.ball_exit_translation[1] > 0 \
            else -game.field.size_y + game.field.line_half_width
        game.can_score = True
        self.interruption('CORNERKICK')

    def goal_kick(self):
        # set the ball at intersection between the centerline and touchline
        game.ball_kick_translation[0] = 0
        game.ball_kick_translation[1] = game.field.size_y - game.field.line_half_width if game.ball_exit_translation[1] > 0 \
            else -game.field.size_y + game.field.line_half_width
        game.can_score = True
        self.interruption('GOALKICK')

    def move_ball_away(self):
        """Places ball far away from field for phases where the referee is supposed to hold it in it's hand"""
        target_location = [100, 100, game.ball_radius + 0.05]
        game.ball.resetPhysics()
        game.ball_translation.setSFVec3f(target_location)
        info("Moved ball out of the field temporarily")

    def kickoff(self):
        color = 'red' if game.kickoff == game.red.id else 'blue'
        info(f'Kick-off is {color}.')
        game.phase = 'KICKOFF'
        game.ball_kick_translation[0] = 0
        game.ball_kick_translation[1] = 0
        game.ball_set_kick = True
        game.ball_first_touch_time = 0
        game.in_play = None
        game.ball_must_kick_team = color
        self.reset_ball_touched()
        game.ball_left_circle = None  # one can score only after ball went out of the circle
        game.can_score = False        # or was touched by another player
        game.can_score_own = False
        game.kicking_player_number = None
        self.move_ball_away()
        info(f'Ball not in play, will be kicked by a player from the {game.ball_must_kick_team} team.')

    def dropped_ball(self):
        info(f'The ball didn\'t move for the past {self.config.DROPPED_BALL_TIMEOUT} seconds.')
        game.ball_last_move = time_count
        self.game_controller_send('DROPPEDBALL')
        game.phase = 'DROPPEDBALL'
        game.ball_kick_translation[0] = 0
        game.ball_kick_translation[1] = 0
        game.ball_set_kick = True
        game.ball_first_touch_time = 0
        game.in_play = None
        game.dropped_ball = True
        game.can_score = True
        game.can_score_own = False

    def is_robot_near(self, position, min_dist):
        for team in [red_team, blue_team]:
            for number in team['players']:
                if distance2(position, team['players'][number]['position']) < min_dist:
                    return True
        return False

    def is_other_robot_near(self, robot_color, robot_number, position, min_dist):
        """Test if another robot than the robot defined by team_color and number is closer than min_dist from position"""
        for team in [red_team, blue_team]:
            for number in team['players']:
                if team['color'] == robot_color and number == robot_number:
                    continue
                if distance2(position, team['players'][number]['position']) < min_dist:
                    return True
        return False

    def reset_pos_penalized_robots_near(self, position, min_dist):
        for team in [red_team, blue_team]:
            for number in team['players']:
                player = team['players'][number]
                if 'penalized' in player and distance2(position, player['position']) < min_dist:
                    self.place_player_at_penalty(player, team, number)

    def penalize_fallen_robots_near(self, position, min_dist):
        for team in [red_team, blue_team]:
            for number in team['players']:
                player = team['players'][number]
                if 'fallen' in player:
                    # If we wait for the end of the tick, the rest of the game interruption procedure will ignore the penalty
                    self.place_player_at_penalty(player, team, number)
                    self.send_penalty(player, "INCAPABLE", "Fallen close to ball during GameInterruption")

    def get_alternative_ball_locations(self, original_pos):
        prefered_x_dir = 1 if (game.interruption_team == game.red.id) ^ (game.side_left == game.blue.id) else -1
        prefered_y_dir = -1 if original_pos[1] > 0 else 1
        offset_x = prefered_x_dir * game.field.place_ball_safety_dist * np.array([1, 0, 0])
        offset_y = prefered_y_dir * game.field.place_ball_safety_dist * np.array([0, 1, 0])
        locations = []
        if game.interruption == "DIRECT_FREEKICK" or game.interruption == "INDIRECT_FREEKICK":
            # TODO If indirect free kick in opponent penalty area on line parallel to goal line, move it along this line
            for dist_mult in range(1, self.config.GAME_INTERRUPTION_PLACEMENT_NB_STEPS+1):
                locations.append(original_pos + offset_x * dist_mult)
                locations.append(original_pos + offset_y * dist_mult)
                locations.append(original_pos - offset_y * dist_mult)
                locations.append(original_pos - offset_x * dist_mult)
        elif game.interruption == "THROWIN":
            for dist_mult in range(1, self.config.GAME_INTERRUPTION_PLACEMENT_NB_STEPS+1):
                locations.append(original_pos + offset_x * dist_mult)
            for dist_mult in range(1, self.config.GAME_INTERRUPTION_PLACEMENT_NB_STEPS+1):
                locations.append(original_pos - offset_x * dist_mult)
        return locations

    def get_obstacles_positions(self, team, number):
        """Returns the list of potential obstacles in case the indicated robot is moved"""
        # TODO: add goal posts for safety
        obstacles = []
        for o_team in [blue_team, red_team]:
            for o_number in o_team['players']:
                if team['color'] == o_team['color'] and number == o_number:
                    continue
                obstacles.append(o_team['players'][o_number]['position'])
        return obstacles

    def move_robots_away(self, target_location):
        for team in [blue_team, red_team]:
            for number in team['players']:
                player = team['players'][number]
                if player['robot'] is None:
                    continue
                initial_pos = np.array(player['position'])
                if distance2(initial_pos, target_location) < game.field.place_ball_safety_dist:
                    obstacles = self.get_obstacles_positions(team, number)
                    player_2_ball = initial_pos - np.array(target_location)
                    dist = np.linalg.norm(player_2_ball[:2])
                    if dist < 0.001:
                        player_2_ball = [1, 0, 0]
                        dist = 1
                    offset = player_2_ball / dist * game.field.place_ball_safety_dist
                    for dist_mult in range(1, self.config.GAME_INTERRUPTION_PLACEMENT_NB_STEPS+1):
                        allowed = True
                        pos = target_location + offset * dist_mult
                        for o in obstacles:
                            if distance2(o, pos) < game.field.place_ball_safety_dist:
                                allowed = False
                                break
                        if allowed:
                            pos[2] = initial_pos[2]
                            diff = pos - initial_pos
                            initial_t = np.array(player['robot'].getField('translation').getSFVec3f())
                            dst_t = initial_t + diff
                            info(f"Moving {team['color']} player {number} from {initial_pos} to {pos}")
                            # Pose of the robot is not changed
                            player['robot'].getField('translation').setSFVec3f(dst_t.tolist())
                            player['position'] = dst_t.tolist()
                            break

    def game_interruption_place_ball(self, target_location, enforce_distance=True):
        if enforce_distance:
            target_location[2] = 0  # Set position along z-axis to 0 for all 'game.field.point_inside' checks
            step = 1
            info(f"GI placing ball to {target_location}")
            while step <= 4 and self.is_robot_near(target_location, game.field.place_ball_safety_dist):
                if step == 1:
                    info('Reset of penalized robots')
                    self.reset_pos_penalized_robots_near(target_location, game.field.place_ball_safety_dist)
                elif step == 2:
                    info('Penalizing fallen robots')
                    self.penalize_fallen_robots_near(target_location, game.field.place_ball_safety_dist)
                elif step == 3:
                    info('Finding alternative locations')
                    for loc in self.get_alternative_ball_locations(target_location):
                        info(f"Testing alternative location: {loc}")
                        # TODO: ?should it only allow point outside penalty area?
                        if game.field.point_inside(loc) and not self.is_robot_near(loc, game.field.place_ball_safety_dist):
                            info(f"Set alternative location to: {loc}")
                            target_location = loc.tolist()
                            break
                elif step == 4:
                    info(f"Pushing robots away from {target_location}")
                    self.move_robots_away(target_location)
                step += 1
        target_location[2] = game.ball_radius
        game.ball.resetPhysics()
        game.ball_translation.setSFVec3f(target_location)
        game.ball_set_kick = False
        self.reset_ball_touched()
        info(f'Ball respawned at {target_location[0]} {target_location[1]} {target_location[2]}.')

    def read_team(self, json_path):
        team = None
        try:
            with open(json_path) as json_file:
                team = json.load(json_file)
                for field_name in ["name", "players"]:
                    if field_name not in team:
                        raise RuntimeError(f"Missing field {field_name}")
                if len(team['players']) == 0:
                    warning(f"No players found for team {team['name']}")
                count = 1
                for p_key, p in team['players'].items():
                    if int(p_key) != count:
                        raise RuntimeError(f'Wrong team player number: expecting "{count}", found "{p_key}".')
                    for field_name in ['proto', 'halfTimeStartingPose', 'reentryStartingPose', 'shootoutStartingPose',
                                       'goalKeeperStartingPose']:
                        if field_name not in p:
                            raise RuntimeError(f"Missing field {field_name} in player {p_key}")
                    count += 1
        except Exception:
            error(f"Failed to read file {json_path} with the following error:\n{traceback.format_exc()}")
            self.clean_exit()
        return team

    def setup(self):
        # if the game.json file is malformed with ids defined as string instead of int, we need to convert them to int:
        if not isinstance(game.red.id, int):
            game.red.id = int(game.red.id)
        if not isinstance(game.blue.id, int):
            game.blue.id = int(game.blue.id)

        # finalize the game object
        if not hasattr(game, 'minimum_real_time_factor'):
            game.minimum_real_time_factor = 3  # we garantee that each time step lasts at least 3x simulated time
        if game.minimum_real_time_factor == 0:  # speed up non-real time tests
            REAL_TIME_BEFORE_FIRST_READY_STATE = 5
            HALF_TIME_BREAK_REAL_TIME_DURATION = 2
        if not hasattr(game, 'press_a_key_to_terminate'):
            game.press_a_key_to_terminate = False
        if game.type not in ['NORMAL', 'KNOCKOUT', 'PENALTY']:
            error(f'Unsupported game type: {game.type}.')
            self.clean_exit()
        game.penalty_shootout = game.type == 'PENALTY'
        info(f'Minimum real time factor is set to {game.minimum_real_time_factor}.')
        if game.minimum_real_time_factor == 0:
            info('Simulation will run as fast as possible, real time waiting times will be minimal.')
        else:
            info(f'Simulation will guarantee a maximum {1 / game.minimum_real_time_factor:.2f}x speed for each time step.')
        field_size = getattr(game, 'class').lower()
        game.field = Field(field_size)


        red_team['color'] = 'red'
        blue_team['color'] = 'blue'
        self.init_team(red_team)
        self.init_team(blue_team)

        # check team name length (should be at most 12 characters long, trim them if too long)
        if len(red_team['name']) > 12:
            red_team['name'] = red_team['name'][:12]
        if len(blue_team['name']) > 12:
            blue_team['name'] = blue_team['name'][:12]

        # check if the host parameter of the game.json file correspond to the actual host
        host = socket.gethostbyname(socket.gethostname())
        if host != '127.0.0.1' and host != game.host:
            warning(f'Host is not correctly defined in game.json file, it should be {host} instead of {game.host}.')

        try:
            JAVA_HOME = os.environ['JAVA_HOME']
            try:
                GAME_CONTROLLER_HOME = os.environ['GAME_CONTROLLER_HOME']
                if not os.path.exists(GAME_CONTROLLER_HOME):
                    error(f'{GAME_CONTROLLER_HOME} (GAME_CONTROLLER_HOME) folder not found.')
                    game.controller_process = None
                    self.clean_exit()
                else:
                    path = os.path.join(GAME_CONTROLLER_HOME, 'build', 'jar', 'config', f'hl_sim_{field_size}', 'teams.cfg')
                    red_line = f'{game.red.id}={red_team["name"]}\n'
                    blue_line = f'{game.blue.id}={blue_team["name"]}\n'
                    with open(path, 'w') as file:
                        file.write((red_line + blue_line) if game.red.id < game.blue.id else (blue_line + red_line))
                    command_line = [os.path.join(JAVA_HOME, 'bin', 'java'), '-jar', 'GameControllerSimulator.jar']
                    if game.minimum_real_time_factor < 1:
                        command_line.append('--fast')
                    command_line.append('--minimized')
                    command_line.append('--config')
                    command_line.append(game_config_file)
                    if hasattr(game, 'game_controller_extra_args'):
                        for arg in game.game_controller_extra_args:
                            command_line.append(arg)
                    if hasattr(game, 'use_bouncing_server') and game.use_bouncing_server:
                        command_line.append('-b')
                        command_line.append(game.host)
                        udp_bouncer_process = subprocess.Popen(["python3", "udp_bouncer.py", game_config_file])
                    else:
                        udp_bouncer_process = None
                    game.controller_process = subprocess.Popen(command_line, cwd=os.path.join(GAME_CONTROLLER_HOME, 'build', 'jar'))
            except KeyError:
                GAME_CONTROLLER_HOME = None
                game.controller_process = None
                error('GAME_CONTROLLER_HOME environment variable not set, unable to launch GameController.')
                self.clean_exit()
        except KeyError:
            JAVA_HOME = None
            GAME_CONTROLLER_HOME = None
            game.controller_process = None
            error('JAVA_HOME environment variable not set, unable to launch GameController.')
            self.clean_exit()

        self.toss_a_coin_if_needed('side_left')
        self.toss_a_coin_if_needed('kickoff')

        children = self.supervisor.getRoot().getField('children')
        children.importMFNodeFromString(-1, f'RobocupSoccerField {{ size "{field_size}" }}')
        ball_size = 1 if field_size == 'kid' else 5
        # the ball is initially very far away from the field
        children.importMFNodeFromString(-1, f'DEF BALL RobocupSoccerBall {{ translation 100 100 0.5 size {ball_size} }}')

        game.state = None
        self.spawn_team(red_team, game.side_left == game.blue.id, children)
        self.spawn_team(blue_team, game.side_left == game.red.id, children)

        display = Display(self.blackboard, self.config.FONT_SIZE, self.config.FONT)
        display.setup_display()

        SIMULATED_TIME_INTERRUPTION_PHASE_0 = int(self.config.SIMULATED_TIME_INTERRUPTION_PHASE_0 * 1000 / time_step)
        SIMULATED_TIME_BEFORE_PLAY_STATE = int(self.config.SIMULATED_TIME_BEFORE_PLAY_STATE * 1000 / time_step)
        SIMULATED_TIME_SET_PENALTY_SHOOTOUT = int(self.config.SIMULATED_TIME_SET_PENALTY_SHOOTOUT * 1000 / time_step)
        players_ball_holding_time_window_size = int(1000 * self.config.PLAYERS_BALL_HOLDING_TIMEOUT / time_step)
        goalkeeper_ball_holding_time_window_size = int(1000 * self.config.GOALKEEPER_BALL_HOLDING_TIMEOUT / time_step)
        red_team['players_holding_time_window'] = np.zeros(players_ball_holding_time_window_size, dtype=bool)
        red_team['goalkeeper_holding_time_window'] = np.zeros(goalkeeper_ball_holding_time_window_size, dtype=bool)
        blue_team['players_holding_time_window'] = np.zeros(players_ball_holding_time_window_size, dtype=bool)
        blue_team['goalkeeper_holding_time_window'] = np.zeros(goalkeeper_ball_holding_time_window_size, dtype=bool)


        self.list_solids()  # prepare lists of solids to monitor in each robot to compute the convex hulls

        self.reset_ball_touched()

        self.previous_seconds_remaining = 0

        try:
            if game.controller_process:
                game.controller = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                retry = 0
                while True:
                    try:
                        game.controller.connect(('localhost', 8750))
                        game.controller.setblocking(False)
                        break
                    except socket.error as msg:
                        retry += 1
                        if retry <= 10:
                            warning(f'Could not connect to GameController at localhost:8750: {msg}. Retrying ({retry}/10)...')
                            time.sleep(retry)  # give some time to allow the GameControllerSimulator to start-up
                            self.supervisor.step(0)
                        else:
                            error('Could not connect to GameController at localhost:8750.')
                            game.controller = None
                            self.clean_exit()
                            break
                info('Connected to GameControllerSimulator at localhost:8750.')
                try:
                    game.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
                    game.udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    if hasattr(game, 'use_bouncing_server') and game.use_bouncing_server:
                        # In case we are using the bouncing server we have to select which interface is used because messages are not
                        # broadcast
                        game.udp.bind((game.host, 3838))
                    else:
                        game.udp.bind(('0.0.0.0', 3838))
                    game.udp.setblocking(False)
                except Exception:
                    error("Failed to set up UDP socket to listen to GC messages")
            else:
                game.controller = None
        except Exception:
            error(f"Failed connecting to GameController with the following exception {traceback.format_exc()}")
            self.clean_exit()

        try:
            self.update_state_display()
            info(f'Game type is {game.type}.')
            info(f'Red team is "{red_team["name"]}", playing on {"left" if game.side_left == game.red.id else "right"} side.')
            info(f'Blue team is "{blue_team["name"]}", playing on {"left" if game.side_left == game.blue.id else "right"} side.')
            game_controller_send(f'SIDE_LEFT:{game.side_left}')

            if hasattr(game, 'supervisor'):  # optional supervisor used for CI tests
                children.importMFNodeFromString(-1, f'DEF TEST_SUPERVISOR Robot {{ supervisor TRUE controller "{game.supervisor}" }}')

            if game.penalty_shootout:
                info(f'{"Red" if game.kickoff == game.red.id else "Blue"} team will start the penalty shoot-out.')
                game.phase = 'PENALTY-SHOOTOUT'
                game.ready_real_time = None
                info(f'Penalty start: Waiting {self.config.REAL_TIME_BEFORE_FIRST_READY_STATE} seconds (real-time) before going to SET')
                game.set_real_time = time.time() + self.config.REAL_TIME_BEFORE_FIRST_READY_STATE  # real time for set state (penalty-shootout)
                self.game_controller_send(f'KICKOFF:{game.kickoff}')
            else:
                info(f'Regular start: Waiting {self.config.REAL_TIME_BEFORE_FIRST_READY_STATE} seconds (real-time) before going to READY')
                game.ready_real_time = time.time() + self.config.REAL_TIME_BEFORE_FIRST_READY_STATE  # real time for ready state (initial kick-off)
                self.kickoff()
                self.game_controller_send(f'KICKOFF:{game.kickoff}')
        except Exception:
            error(f"Failed setting initial state: {traceback.format_exc()}")
            self.clean_exit()

        if hasattr(game, 'record_simulation'):
            try:
                if game.record_simulation.endswith(".html"):
                    self.supervisor.animationStartRecording(game.record_simulation)
                elif game.record_simulation.endswith(".mp4"):
                    self.supervisor.movieStartRecording(game.record_simulation, width=1280, height=720, codec=0, quality=100,
                                                   acceleration=1, caption=False)
                    if self.supervisor.movieFailed():
                        raise RuntimeError("Failed to Open Movie")
                else:
                    raise RuntimeError(f"Unknown extension for record_simulation: {game.record_simulation}")
            except Exception:
                error(f"Failed to start recording with exception: {traceback.format_exc()}")
                self.clean_exit()

    def main_loop(self):
        try:
            previous_real_time = time.time()
            while self.supervisor.step(time_step) != -1 and not game.over:
                if hasattr(game, 'max_duration') and (time.time() - log.real_time) > game.max_duration:
                    info(f'Interrupting game automatically after {game.max_duration} seconds')
                    break
                self.perform_status_update()
                self.game_controller_send(f'CLOCK:{time_count}')
                self.game_controller_receive()
                if game.state is None:
                    time_count += time_step
                    continue
                self.stabilize_robots()
                send_play_state_after_penalties = False
                previous_position = copy.deepcopy(game.ball_position)
                game.ball_position = game.ball_translation.getSFVec3f()
                if game.ball_position != previous_position:
                    game.ball_last_move = time_count
                self.update_contacts()  # check for collisions with the ground and ball
                if not game.penalty_shootout:
                    self.update_ball_holding()  # check for ball holding for field players and goalkeeper
                self.update_histories()
                if game.state.game_state == 'STATE_PLAYING' and not self.is_early_game_interruption():
                    self.check_outside_turf()
                    self.check_forceful_contacts()
                    self.check_inactive_goalkeepers()
                    if game.in_play is None:
                        # During period after the end of a game interruption, check distance of opponents
                        if game.phase in GAME_INTERRUPTIONS and game.state.secondary_state[6:] == "NORMAL":
                            opponent_team = red_team if game.ball_must_kick_team == 'blue' else blue_team
                            self.check_team_away_from_ball(opponent_team, game.field.opponent_distance_to_ball)
                        # If ball is not in play after a kick_off, check for circle entrance for the defending team
                        if game.phase == 'KICKOFF' and game.kickoff != self.config.DROPPED_BALL_TEAM_ID:
                            defending_team = red_team if game.kickoff == game.blue.id else blue_team
                            self.check_circle_entrance(defending_team)
                        if game.ball_first_touch_time != 0:
                            d = distance2(game.ball_kick_translation, game.ball_position)
                            if d > self.config.BALL_IN_PLAY_MOVE:
                                info(f'{game.ball_kick_translation} {game.ball_position}')
                                info(f'Ball in play, can be touched by any player (moved by {d * 100:.2f} cm).')
                                game.in_play = time_count
                            elif not self.is_game_interruption():  # The game interruption case is handled in update_team_contacts
                                team = red_team if game.ball_must_kick_team == 'blue' else blue_team
                                self.check_ball_must_kick(team)
                    else:
                        if time_count - game.ball_last_move > self.config.DROPPED_BALL_TIMEOUT * 1000:
                            self.dropped_ball()
                        if game.ball_left_circle is None and game.phase == 'KICKOFF':
                            if distance2(game.ball_kick_translation, game.ball_position) > game.field.circle_radius + game.ball_radius:
                                game.ball_left_circle = time_count
                                info('The ball has left the center circle after kick-off.')

                        ball_touched_by_opponent = game.ball_last_touch_team and (game.ball_last_touch_team != game.ball_must_kick_team)
                        ball_touched_by_teammate = (game.kicking_player_number is not None and
                                                    game.ball_last_touch_player_number != game.kicking_player_number)
                        ball_touched_in_play = game.in_play is not None and game.in_play < game.ball_last_touch_time
                        if not game.can_score:
                            if game.phase == 'KICKOFF':
                                ball_touched_after_leaving_the_circle = game.ball_left_circle is not None \
                                                                        and game.ball_left_circle < game.ball_last_touch_time
                                if ball_touched_by_opponent or ball_touched_by_teammate or ball_touched_after_leaving_the_circle:
                                    game.can_score = True
                            elif game.phase == 'THROWIN':
                                if ball_touched_by_teammate or ball_touched_by_opponent or ball_touched_in_play:
                                    game.can_score = True
                        if not game.can_score_own:
                            if ball_touched_by_opponent or ball_touched_by_teammate or ball_touched_in_play:
                                game.can_score_own = True

                    if game.penalty_shootout:
                        self.check_penalty_goal_line()
                        ball_in_goal_area = game.field.circle_fully_inside_goal_area(game.ball_position, game.ball_radius)
                        # It is unclear that using getVelocity is the good approach, because even when the ball is clearly not moving
                        # anymore, it still provides values above 1e-3.
                        ball_vel = game.ball.getVelocity()[:3]
                        if ball_in_goal_area and np.linalg.norm(ball_vel) < self.config.STATIC_SPEED_EPS:
                            info(f"Ball stopped in goal area at {game.ball_position}")
                            self.next_penalty_shootout()
                        if game.penalty_shootout_count < 10:  # detect entrance of kicker in the goal area
                            kicker = self.penalty_kicker_player()
                            if kicker is None or (not kicker['outside_goal_area'] and not kicker['inside_own_side']):
                                # if no kicker is available or if the kicker is not fully outside the opponent goal area,
                                # we stop the kick and continue
                                self.next_penalty_shootout()
                                if game.over:
                                    break
                        else:  # extended penalty shootouts
                            if ball_in_goal_area:
                                c = game.penalty_shootout_count - 10
                                if game.penalty_shootout_time_to_reach_goal_area[c] is None:
                                    game.penalty_shootout_time_to_reach_goal_area[c] = 60 - game.state.seconds_remaining
                    if self.previous_seconds_remaining != game.state.seconds_remaining:
                        self.update_state_display()
                        self.previous_seconds_remaining = game.state.seconds_remaining
                        # TODO find out why GC can send negative 'seconds_remaining' when secondary state is penaltykick
                        if game.state.game_state != "STATE_FINISHED" and game.state.seconds_remaining <= 0 and \
                                not game.state.secondary_state == "PENALTYKICK":
                            info(f"Sending FINISH because seconds remaining = {game.state.seconds_remaining}")
                            self.game_controller_send('STATE:FINISH')
                            if game.penalty_shootout:  # penalty timeout was reached
                                self.next_penalty_shootout()
                                if game.over:
                                    break
                            elif game.state.first_half:
                                game_type = 'knockout ' if game.type == 'KNOCKOUT' and game.overtime else ''
                                info(f'End of {game_type} first half.')
                                self.flip_sides()
                                self.reset_teams('halfTimeStartingPose')
                                game.kickoff = game.blue.id if game.kickoff == game.red.id else game.red.id
                            elif game.type == 'NORMAL':
                                info('End of second half.')
                            elif game.type == 'KNOCKOUT':
                                if not game.overtime:
                                    info('End of second half.')
                                    self.flip_sides()
                                    self.reset_teams('halfTimeStartingPose')
                                    game.kickoff = game.blue.id if game.kickoff == game.red.id else game.red.id
                                    game.overtime = True
                                else:
                                    info('End of knockout second half.')
                                    game.finished_overtime = True
                            else:
                                error(f'Unsupported game type: {game.type}.')
                                self.clean_exit()
                    if (game.interruption_countdown == 0 and game.ready_countdown == 0 and
                            game.ready_real_time is None and not game.throw_in and
                            (game.ball_position[1] - game.ball_radius >= game.field.size_y or
                             game.ball_position[1] + game.ball_radius <= -game.field.size_y or
                             game.ball_position[0] - game.ball_radius >= game.field.size_x or
                             game.ball_position[0] + game.ball_radius <= -game.field.size_x)):
                        info(f'Ball left the field at ({game.ball_position[0]} {game.ball_position[1]} {game.ball_position[2]}) after '
                             f'being touched by {game.ball_last_touch_team} player {game.ball_last_touch_player_number}.')
                        game.ball_exit_translation = game.ball_position
                        scoring_team = None
                        right_way = None
                        if game.ball_exit_translation[1] - game.ball_radius > game.field.size_y:
                            if game.penalty_shootout:
                                self.next_penalty_shootout()
                            else:
                                game.ball_exit_translation[1] = game.field.size_y - game.field.line_half_width
                                self.throw_in(left_side=False)
                        elif game.ball_exit_translation[1] + game.ball_radius < -game.field.size_y:
                            if game.penalty_shootout:
                                self.next_penalty_shootout()
                            else:
                                self.throw_in(left_side=True)
                        if game.ball_exit_translation[0] - game.ball_radius > game.field.size_x:
                            right_way = game.ball_last_touch_team == 'red' and game.side_left == game.red.id or \
                                        game.ball_last_touch_team == 'blue' and game.side_left == game.blue.id
                            if game.ball_exit_translation[1] < self.config.GOAL_HALF_WIDTH and \
                                    game.ball_exit_translation[1] > -self.config.GOAL_HALF_WIDTH and \
                                    game.ball_exit_translation[2] < game.field.goal_height:
                                scoring_team = game.side_left  # goal
                            elif game.penalty_shootout:
                                self.next_penalty_shootout()
                            else:
                                if right_way:
                                    self.goal_kick()
                                else:
                                    self.corner_kick(left_side=False)
                        elif game.ball_exit_translation[0] + game.ball_radius < -game.field.size_x:
                            right_way = game.ball_last_touch_team == 'red' and game.side_left == game.blue.id or \
                                        game.ball_last_touch_team == 'blue' and game.side_left == game.red.id
                            if game.ball_exit_translation[1] < self.config.GOAL_HALF_WIDTH and \
                                    game.ball_exit_translation[1] > -self.config.GOAL_HALF_WIDTH and \
                                    game.ball_exit_translation[2] < game.field.goal_height:
                                # goal
                                scoring_team = game.red.id if game.blue.id == game.side_left else game.blue.id
                            elif game.penalty_shootout:
                                self.next_penalty_shootout()
                            else:
                                if right_way:
                                    self.goal_kick()
                                else:
                                    self.corner_kick(left_side=True)
                        if scoring_team:
                            goal = 'red' if scoring_team == game.blue.id else 'blue'
                            if game.penalty_shootout_count >= 10:  # extended penalty shootouts
                                extended_penalty_idx = game.penalty_shootout_count - 10
                                game.penalty_shootout_time_to_score[extended_penalty_idx] = 60 - game.state.seconds_remaining
                            if not game.penalty_shootout:
                                game.kickoff = game.blue.id if scoring_team == game.red.id else game.red.id
                            i = self.team_index(game.ball_last_touch_team)
                            if not game.can_score:
                                if game.phase == 'KICKOFF':
                                    info(f'Invalidated direct score in {goal} goal from kick-off position.')
                                    self.goal_kick()
                                elif game.phase in GAME_INTERRUPTIONS:
                                    info(f'Invalidated direct score in {goal} goal from {GAME_INTERRUPTIONS[game.phase]}.')
                                    if not right_way:  # own_goal
                                        self.corner_kick(left_side=scoring_team != game.side_left)
                                    else:
                                        self.goal_kick()

                            elif not right_way and not game.can_score_own:
                                if game.phase == 'KICKOFF':
                                    info(f'Invalidated direct score in {goal} goal from kick-off position.')
                                elif game.phase in GAME_INTERRUPTIONS:
                                    info(f'Invalidated direct score in {goal} goal from {GAME_INTERRUPTIONS[game.phase]}.')
                                if game.penalty_shootout:
                                    self.next_penalty_shootout()
                                else:
                                    self.corner_kick(left_side=scoring_team != game.side_left)

                            elif (game.ball_last_touch_player_number is not None and
                                  game.state.teams[i].players[game.ball_last_touch_player_number - 1].secs_till_unpenalized == 0):
                                self.game_controller_send(f'SCORE:{scoring_team}')
                                info(f'Score in {goal} goal by {game.ball_last_touch_team} player {game.ball_last_touch_player_number}')
                                if game.penalty_shootout:
                                    game.penalty_shootout_goal = True
                                    self.next_penalty_shootout()
                                else:
                                    game.ready_countdown = self.config.SIMULATED_TIME_INTERRUPTION_PHASE_0
                                    info(f"Ready countdown was set to {game.ready_countdown}")
                                    self.kickoff()
                            elif not right_way:  # own goal
                                self.game_controller_send(f'SCORE:{scoring_team}')
                                info(f'Score in {goal} goal by {game.ball_last_touch_team} player ' +
                                     f'{game.ball_last_touch_player_number} (own goal)')
                                game.ready_countdown = self.config.SIMULATED_TIME_INTERRUPTION_PHASE_0
                                info(f"Ready countdown was set to {game.ready_countdown}")
                                self.kickoff()
                            else:
                                info(f'Invalidated score in {goal} goal by penalized ' +
                                     f'{game.ball_last_touch_team} player {game.ball_last_touch_player_number}')
                                if game.penalty_shootout:
                                    self.next_penalty_shootout()
                                else:
                                    self.goal_kick()
                elif game.state.game_state == 'STATE_READY':
                    game.play_countdown = 0
                    # the GameController will automatically change to the SET state once the state READY is over
                    # the referee should wait a little time since the state SET started before sending the PLAY state
                elif game.state.game_state == 'STATE_SET':
                    if game.play_countdown == 0:
                        if game.penalty_shootout:
                            info("Waiting for penalty shootout")
                            game.play_countdown = self.config.SIMULATED_TIME_SET_PENALTY_SHOOTOUT
                        else:
                            info("Waiting for classic play")
                            game.play_countdown = self.config.SIMULATED_TIME_BEFORE_PLAY_STATE
                        if game.ball_set_kick:
                            self.game_interruption_place_ball(game.ball_kick_translation, enforce_distance=False)
                    else:
                        if game.penalty_shootout:
                            self.check_penalty_goal_line()
                        else:
                            if game.dropped_ball:
                                self.check_dropped_ball_position()
                            else:
                                self.check_kickoff_position()
                        game.play_countdown -= 1
                        if game.play_countdown == 0:
                            game.ready_countdown = 0
                            send_play_state_after_penalties = True
                elif game.state.game_state == 'STATE_FINISHED':
                    if game.penalty_shootout:
                        if game.state.seconds_remaining <= 0:
                            self.next_penalty_shootout()
                    elif game.state.first_half:
                        info("Received state FINISHED: end of first half")
                        game.ready_real_time = None
                    elif game.type == 'KNOCKOUT':
                        if game.ready_real_time is None:
                            if game.state.teams[0].score != game.state.teams[1].score:
                                game.over = True
                                break
                            elif game.finished_overtime:
                                info('Beginning of penalty shout-out.')
                                self.game_controller_send('STATE:PENALTY-SHOOTOUT')
                                game.penalty_shootout = True
                                info(f'Going to SET in {self.config.HALF_TIME_BREAK_REAL_TIME_DURATION} seconds (real-time)')
                                game.set_real_time = time.time() + self.config.HALF_TIME_BREAK_REAL_TIME_DURATION
                            elif game.overtime:
                                info('Beginning of the knockout first half.')
                                self.game_controller_send('STATE:OVERTIME-FIRST-HALF')
                                info(f'Going to READY in {self.config.HALF_TIME_BREAK_REAL_TIME_DURATION} seconds (real-time)')
                                game.ready_real_time = time.time() + self.config.HALF_TIME_BREAK_REAL_TIME_DURATION
                    else:
                        game.over = True
                        break

                elif game.state.game_state == 'STATE_INITIAL':
                    if game.penalty_shootout:
                        if game.set_real_time <= time.time():
                            info("Starting first penalty")
                            self.set_penalty_positions()
                            self.game_controller_send('STATE:SET')
                    elif game.ready_real_time is not None:
                        if game.ready_real_time <= time.time():  # initial kick-off (1st, 2nd half, extended periods, penalty shootouts)
                            info('Real-time to wait elasped, moving to READY')
                            game.ready_real_time = None
                            self.check_start_position()
                            self.game_controller_send('STATE:READY')
                    elif game.ready_countdown > 0:
                        game.ready_countdown -= 1
                        if game.ready_countdown == 0:  # kick-off after goal or dropped ball
                            self.check_start_position()
                            self.game_controller_send('STATE:READY')
                    elif not game.state.first_half:
                        game_type = ''
                        if game.overtime:
                            game_type = 'overtime '
                        info(f'Beginning of {game_type}second half.')
                        self.kickoff()
                        info(f'Going to READY in {self.config.HALF_TIME_BREAK_REAL_TIME_DURATION} seconds (real-time)')
                        game.ready_real_time = time.time() + self.config.HALF_TIME_BREAK_REAL_TIME_DURATION

                if game.interruption_countdown > 0:
                    game.interruption_countdown -= 1
                    if game.interruption_countdown == 0:
                        if game.ball_set_kick:
                            self.game_interruption_place_ball(game.ball_kick_translation, enforce_distance=True)
                        if game.interruption:
                            self.game_controller_send(f'{game.interruption}:{game.interruption_team}:READY')

                if game.state.game_state != 'STATE_INITIAL':
                    self.check_fallen()                                # detect fallen robots

                if game.state.game_state == 'STATE_PLAYING' and game.in_play:
                    if not game.penalty_shootout:
                        ball_holding = self.check_ball_holding()       # check for ball holding fouls
                        if ball_holding:
                            self.interruption('FREEKICK', ball_holding, game.ball_position)
                    ball_handling = check_ball_handling()  # return team id if ball handling is performed by goalkeeper
                    if ball_handling and not game.penalty_shootout:
                        self.interruption('FREEKICK', ball_handling, game.ball_position, is_goalkeeper_ball_manipulation=True)
                self.check_penalized_in_field()                    # check for penalized robots inside the field
                if game.state.game_state != 'STATE_INITIAL':  # send penalties if needed
                    self.send_penalties()
                    if send_play_state_after_penalties:
                        self.game_controller_send('STATE:PLAY')
                        send_play_state_after_penalties = False

                time_count += time_step

                if game.minimum_real_time_factor != 0:
                    # slow down the simulation to guarantee a miminum amount of real time between each step
                    t = time.time()
                    delta_time = previous_real_time - t + game.minimum_real_time_factor * time_step / 1000
                    if delta_time > 0:
                        time.sleep(delta_time)
                    previous_real_time = time.time()

            if not game.over:  # for some reason, the simulation was terminated before the end of the match (may happen during tests)
                info('Game interrupted before the end.')
            else:
                info('End of the game.')
                if game.state.teams[0].score > game.state.teams[1].score:
                    winner = 0
                    loser = 1
                else:
                    winner = 1
                    loser = 0
                info(f'The score is {game.state.teams[winner].score}-{game.state.teams[loser].score}.')
                if game.state.teams[0].score != game.state.teams[1].score:
                    info(f'The winner is the {game.state.teams[winner].team_color.lower()} team.')
                elif game.penalty_shootout_count < 20:
                    info('This is a draw.')
                else:  # extended penatly shoutout rules to determine the winner
                    count = [0, 0]
                    for i in range(5):
                        if game.penalty_shootout_time_to_reach_goal_area[2 * i] is not None:
                            count[0] += 1
                        if game.penalty_shootout_time_to_reach_goal_area[2 * i + 1] is not None:
                            count[1] += 1
                    if game.kickoff == game.red.id:
                        count_red = count[0]
                        count_blue = count[1]
                    else:
                        count_red = count[1]
                        count_blue = count[0]
                    info('The during the extended penalty shootout, ' +
                         f'the ball reached the red goal area {count_blue} times and the blue goal area {count_red} times.')
                    if count_red > count_blue:
                        info('The winner is the red team.')
                    elif count_blue > count_red:
                        info('The winner is the blue team.')
                    else:
                        count = [0, 0]
                        for i in range(5):
                            if game.penalty_shootout_time_to_touch_ball[2 * i] is not None:
                                count[0] += 1
                            if game.penalty_shootout_time_to_touch_ball[2 * i + 1] is not None:
                                count[1] += 1
                        if game.kickoff == game.red.id:
                            count_red = count[0]
                            count_blue = count[1]
                        else:
                            count_red = count[1]
                            count_blue = count[0]
                        info(f'The ball was touched {count_red} times by the red player and {count_blue} times by the blue player.')
                        if count_red > count_blue:
                            info('The winner is the red team.')
                        elif count_blue > count_red:
                            info('The winner is the blue team.')
                        else:
                            sum = [0, 0]
                            for i in range(5):
                                t = game.penalty_shootout_time_to_score[2 * i]
                                sum[0] += 60 if t is None else t
                                t = game.penalty_shootout_time_to_score[2 * i + 1]
                                sum[1] += 60 if t is None else t
                            if game.kickoff == game.red.id:
                                sum_red = sum[0]
                                sum_blue = sum[1]
                            else:
                                sum_red = sum[1]
                                sum_blue = sum[0]
                            info(f'The red team took {sum_red} seconds to score while blue team took {sum_blue} seconds.')
                            if sum_blue < sum_red:
                                info('The winner is the blue team.')
                            elif sum_red < sum_blue:
                                info('The winner is the red team.')
                            else:
                                sum = [0, 0]
                                for i in range(5):
                                    t = game.penalty_shootout_time_to_reach_goal_area[2 * i]
                                    sum[0] += 60 if t is None else t
                                    t = game.penalty_shootout_time_to_reach_goal_area[2 * i + 1]
                                    sum[1] += 60 if t is None else t
                                if game.kickoff == game.red.id:
                                    sum_red = sum[0]
                                    sum_blue = sum[1]
                                else:
                                    sum_red = sum[1]
                                    sum_blue = sum[0]
                                info(f'The red team took {sum_red} seconds to send the ball to the goal area ' +
                                     f'while blue team took {sum_blue} seconds.')
                                if sum_blue < sum_red:
                                    info('The winner is the blue team.')
                                elif sum_red < sum_blue:
                                    info('The winner is the red team.')
                                else:
                                    sum = [0, 0]
                                    for i in range(5):
                                        t = game.penalty_shootout_time_to_touch_ball[2 * i]
                                        sum[0] += 60 if t is None else t
                                        t = game.penalty_shootout_time_to_touch_ball[2 * i + 1]
                                        sum[1] += 60 if t is None else t
                                    if game.kickoff == game.red.id:
                                        sum_red = sum[0]
                                        sum_blue = sum[1]
                                    else:
                                        sum_red = sum[1]
                                        sum_blue = sum[0]
                                    info(f'The red team took {sum_red} seconds to touch the ball ' +
                                         f'while blue team took {sum_blue} seconds.')
                                    if sum_blue < sum_red:
                                        info('The winner is the blue team.')
                                    elif sum_red < sum_blue:
                                        info('The winner is the red team.')
                                    else:
                                        info('Tossing a coin to determine the winner.')
                                        if bool(random.getrandbits(1)):
                                            info('The winer is the red team.')
                                        else:
                                            info('The winer is the blue team.')
        except Exception:
            error(f"Unexpected exception in main referee loop: {traceback.format_exc()}")
            self.clean_exit()

        self.clean_exit()
