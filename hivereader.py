#!/usr/bin/env python

import argparse
import json
import time
import sys
import re
import os

import pyhiveapi as Hive

CMD_LOGIN='login'
CMD_SAVE_DATA='save'
CMD_METRICS='metrics'
CMD_CHECK_BATTERY='battery'

CHOICES=[
    CMD_LOGIN,
    CMD_SAVE_DATA,
    CMD_METRICS,
    CMD_CHECK_BATTERY,
]



class HiveReaderException(Exception):
    pass

class HiveReader:

    def __init__(self, session_file='~/hive-session.json'):
        self.session_file = os.path.expanduser(session_file)
        self.session = self.load_session()

        if self.requires_login():
            return

        self.refresh_token()

        self.api = Hive.API(token=self.session['IdToken'])

        response = self.api.getAll()

        if 'parsed' not in response:
            raise HiveReaderException('No parsed data found')

        self.data = response['parsed']


    def load_session(self):
        try:
            with open(self.session_file, 'r') as session_file:
                return json.load(session_file)
        except FileNotFoundError:
            return {}


    def save_session(self):
        with open(self.session_file, 'w') as session_file:
            json.dump(self.session, session_file, indent=2)


    def requires_login(self):
        if self.session == {}:
            return True

        if 'IdToken' not in self.session:
            return True

        if 'ExpiresAt' not in self.session:
            return True

        return False


    def login(self, username, password):
        if not username or not password:
            raise HiveReaderException('Username and password are required for login')

        auth = Hive.Auth(username, password)
        login_response = auth.login()

        if login_response.get('ChallengeName') != Hive.SMS_REQUIRED:
            session = login_response['AuthenticationResult']
        else:
            code = input('Enter your 2FA code: ')
            mfa_response = auth.sms_2fa(code, login_response)
            session = mfa_response['AuthenticationResult']

        if 'IdToken' not in session:
            raise Hive.NoApiToken

        self.session = session
        self.insert_expires_at()

        self.save_session()


    def refresh_token(self):
        if self.session['ExpiresAt'] > int(time.time()):
            return

        refresh_token_params = {
            'token': self.session['IdToken'],
            'refreshToken': self.session['RefreshToken'],
            'accessToken': self.session['AccessToken'],
        }

        refreshed_tokens = self.api.refreshTokens(refresh_token_params)
        if refreshed_tokens['original'] != 200:
            raise Hive.NoApiToken

        self.session.update({
            'IdToken': refreshed_tokens['parsed']['token'],
            'RefreshToken': refreshed_tokens['parsed']['refreshToken'],
            'AccessToken': refreshed_tokens['parsed']['accessToken'],
        })
        self.insert_expires_at()

        self.save_session()


    def insert_expires_at(self):
        self.session['ExpiresAt'] = int(time.time()) + self.session['ExpiresIn']


    def get_data(self):
        return self.data


    def write_data_json(self, filename):
        with open(filename, 'w') as data_file:
            json.dump(self.data, data_file, indent=2)


    def print_graphite_stats(self):
        now = int(time.time())

        for product in self.data.get('products', []):
            product_type = product['type']
            state = product.get('state', {})
            props = product.get('props', {})
            safe_name = re.sub('[^0-9a-zA-Z]+', '_', state['name']).lower()

            if 'temperature' in props:
                print('hive.{}.temperature {} {}'.format(
                    safe_name,
                    props['temperature'],
                    now,
                ))

            if 'target' in state:
                print('hive.{}.target {} {}'.format(
                    safe_name,
                    state['target'],
                    now,
                ))

            if 'boost' in state:
                print('hive.{}_{}.boost {} {}'.format(
                    safe_name,
                    product_type,
                    int((state.get('boost', 0) or 0) > 0),
                    now,
                ))

        for device in self.data.get('devices', []):
            state = device.get('state', {})
            props = device.get('props', {})
            safe_name = re.sub('[^0-9a-zA-Z]+', '_', state['name']).lower()

            if 'battery' in props:
                print('hive.{}.battery {} {}'.format(
                    safe_name,
                    props['battery'],
                    now,
                ))

    def check_batteries(self, warning_threshold=25, critical_threshold=5):
        warn = []
        crit = []

        for device in self.data.get('devices', []):
            props = device.get('props', {})

            if 'battery' not in props:
                continue

            name = device.get('state', {}).get('name')
            battery = device.get('props', {}).get('battery')
            line = '- {}: {}%'.format(name, battery)

            if battery < critical_threshold:
                crit.append(line)
            elif battery < warning_threshold:
                warn.append(line)

        if len(crit) > 0:
            print('Critically low batteries:')
            print('\n'.join(crit))

        if len(crit) and len(warn):
            print('')

        if len(warn) > 0:
            print('Low batteries:')
            print('\n'.join(warn))

        if len(crit) > 0:
            return 2
        elif len(warn) > 0:
            return 1
        else:
            return 0



def run():
    args = parse_args()

    try:
        reader = HiveReader(session_file=args.session_file)

        if args.command == CMD_LOGIN:
            reader.login(args.username, args.password)

        if reader.requires_login() and args.command != CMD_LOGIN:
            print('Login required');
            sys.exit(3)

        if args.command == CMD_SAVE_DATA:
            reader.write_data_json(args.save_file)

        if args.command == CMD_METRICS:
            reader.print_graphite_stats()

        if args.command == CMD_CHECK_BATTERY:
            status = reader.check_batteries(warning_threshold=args.warning, critical_threshold=args.critical)
            sys.exit(status)
    except Exception as ex:
        print(ex)
        sys.exit(3)


def parse_args():
    parser = argparse.ArgumentParser(description='Clone site')
    parser.add_argument('command', choices=CHOICES)
    parser.add_argument('--username', '-u', help='Your Hive username')
    parser.add_argument('--password', '-p', help='Your Hive password')
    parser.add_argument('--warning', '-w', type=int, default=5, help='Check warning threshold')
    parser.add_argument('--critical', '-c', type=int, default=20, help='Check critical threshold')
    parser.add_argument('--save-file', default='data.json', help='A file to save data to')
    parser.add_argument('--session-file', default='~/hive-session.json', help='The file to save session tokens to')

    return parser.parse_args()


if __name__ == '__main__':
    run()
