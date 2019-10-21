from requests.packages.urllib3.util.retry import Retry
from concurrent.futures import ThreadPoolExecutor
from requests.adapters import HTTPAdapter
from colorama import Fore, init
from copy import deepcopy
import traceback
import requests
import shutil
import time
import json
import sys
import csv
import os

requests.packages.urllib3.disable_warnings()
init(autoreset=True)


class Chromium(object):
    """Download all the chromium old stable versions"""

    def __init__(self, channel='stable'):
        self.channel = channel
        self.strip_chars = ' \r\n\t/"\',\\'
        self.os_type = ['mac', 'win', 'win64', 'linux']
        self.omahaproxy_host = 'https://omahaproxy.appspot.com'
        self.chromium_download_url_template = 'https://www.googleapis.com/download/storage/v1/b/' \
                                              'chromium-browser-snapshots/o/{0}?alt=media'
        status_forcelist = [500, 502, 503, 504, 522, 524, 408, 400, 401, 403]
        retries = Retry(total=5, read=5, connect=5, backoff_factor=3, status_forcelist=status_forcelist)
        self.session = requests.session()
        self.session.mount('http://', HTTPAdapter(max_retries=retries))
        self.session.mount('https://', HTTPAdapter(max_retries=retries))
        self.session.verify = False
        self.chromium_versions = dict()
        self.chromium_position_urls = dict()
        self.chromium_positions = dict()
        self.chromium_downloads = dict()
        self.time_out = 300
        self.position_offset = 10

    @staticmethod
    def check_future_result(futures):
        """Function: check_future_result"""

        for future in futures:
            try:
                future.result()
            except Exception as e:
                print(traceback.format_exc())
                raise Exception('Error: Exception found {0}'.format(e))

    @staticmethod
    def __process_difference(history_json_file, history_json_file_exists, releases):
        """Private Function: __process_difference"""

        if history_json_file_exists is False:
            with open(history_json_file, 'w+') as f:
                json.dump(releases, f)
            return releases
        else:
            with open(history_json_file) as f:
                existed_release = json.loads(f.read())
            new_releases = [x for x in releases if x not in existed_release]
            return new_releases

    def get_chromium_versions(self):
        """Function: get_chromium_versions"""

        print('Info: Start to get all chromium versions...')
        history_json_format = '{0}/history.json?channel={1}&os={2}'
        for os_type in self.os_type:
            url = history_json_format.format(self.omahaproxy_host, self.channel, os_type)
            try:
                res = self.session.get(url, timeout=self.time_out)
                status_code = res.status_code
                content = res.content
                if status_code != 200:
                    warning_message = 'Warning: Unexpected status code ' \
                                      'when requesting history url: {0}, {1}'.format(url, status_code)
                    print(Fore.YELLOW + warning_message)
                    continue
                releases = json.loads(content)
                history_json_file = '{0}.history.json'.format(os_type)
                history_json_file_exists = os.path.exists(history_json_file)
                new_releases = self.__process_difference(history_json_file, history_json_file_exists, releases)
                if not new_releases:
                    print('Info: No new release found, system stopping...')
                    sys.exit(0)
                all_releases = releases + new_releases
                with open(history_json_file, 'w+') as f:
                    json.dump(all_releases, f)
                for release in new_releases:
                    try:
                        version = release['version']
                        self.chromium_versions.setdefault(os_type, []).append(version)
                    except KeyError:
                        pass
            except (requests.RequestException,
                    requests.exceptions.SSLError,
                    requests.packages.urllib3.exceptions.SSLError) as e:
                error_message = 'Error: Unexpected error when requesting history url: {0}, {1}'.format(url, e)
                print(Fore.RED + error_message)

    def prepare_chromium_position_urls(self):
        """Function: get_chromium_position_urls"""

        print('Info: Prepare the position urls...')
        deps_json_format = '{0}/deps.json?version={1}'
        for os_type, versions in self.chromium_versions.items():
            for version in versions:
                url = deps_json_format.format(self.omahaproxy_host, version)
                value = {'version': version, 'position_url': url}
                self.chromium_position_urls.setdefault(os_type, []).append(value)

    def __parallel_requests_to_get_positions(self, os_type, version, position_url):
        """Private Function: __parallel_requests_to_get_positions"""

        try:
            res = self.session.get(position_url, timeout=self.time_out)
            status_code = res.status_code
            content = res.content
            if status_code != 200:
                warning_message = 'Warning: Unexpected status code ' \
                                  'when requesting position url: {0}, {1}'.format(position_url, status_code)
                print(Fore.YELLOW + warning_message)
            else:
                position_json = json.loads(content)
                try:
                    chromium_base_position = int(position_json['chromium_base_position'])
                    value = {'version': version, 'position_url': position_url, 'position': chromium_base_position}
                    self.chromium_positions.setdefault(os_type, []).append(value)
                except (KeyError, TypeError):
                    pass
            time.sleep(5)
        except (requests.RequestException,
                requests.exceptions.SSLError,
                requests.packages.urllib3.exceptions.SSLError) as e:
            error_message = 'Error: Unexpected error when requesting position url: {0}, {1}'.format(position_url, e)
            print(Fore.RED + error_message)

    def get_chromium_positions(self, workers=10):
        """Function: get_chromium_positions

        :param workers: concurrent requests to get the positions (default 3)
        """

        print('Info: Start to get all chromium positions...')
        pool = ThreadPoolExecutor(max_workers=workers)
        futures = list()
        for os_type, values in self.chromium_position_urls.items():
            for value in values:
                version = value['version']
                position_url = value['position_url']
                future = pool.submit(self.__parallel_requests_to_get_positions,
                                     os_type=os_type,
                                     version=version,
                                     position_url=position_url)
                futures.append(future)
        pool.shutdown(wait=True)
        self.check_future_result(futures)

    def __get_chromium_download_url_core(self, name_templates, position, value, os_type, win=False, win64=False):
        """Private Function: __chromium_download_core """

        status_codes = list()
        for chromium_file_name, chromium_download_name_template in name_templates.items():
            chromium_download_name = chromium_download_name_template.format(position)
            chromium_download_url = self.chromium_download_url_template.format(chromium_download_name)
            try:
                res = self.session.head(chromium_download_url, timeout=self.time_out)
                status_code = res.status_code
                if win64 is True and status_code != 200:
                    chromium_download_url = chromium_download_url.replace('chrome-win.zip', 'chrome-win32.zip')
                    res = self.session.head(chromium_download_url, timeout=self.time_out)
                    status_code = res.status_code
                if win is True and status_code != 200:
                    chromium_download_url = chromium_download_url.replace('chrome-win32.zip', 'chrome-win.zip')
                    res = self.session.head(chromium_download_url, timeout=self.time_out)
                    status_code = res.status_code
                status_codes.append(status_code)
                if status_code == 200:
                    time.sleep(5)
                    value['download_position'] = position
                    value['download_url'] = chromium_download_url
                    value['download_name'] = chromium_file_name
                    self.chromium_downloads.setdefault(os_type, []).append(value)
                    print('Info: Find the downloading url {0}...'.format(chromium_download_url))
                time.sleep(5)
            except (requests.RequestException,
                    requests.exceptions.SSLError,
                    requests.packages.urllib3.exceptions.SSLError) as e:
                error_message = 'Error: Unexpected error ' \
                                'when requesting download url: {0}, {1}'.format(chromium_download_url, e)
                print(Fore.RED + error_message)

        return status_codes

    def __parallel_get_download_chromium_url(self, os_type, version, position_url, position):
        """Private Function: __parallel_requests_to_download_chromium"""

        # Format name
        win = False
        win64 = False
        if os_type == 'mac':
            mac_name = 'Mac%2F{0}%2Fchrome-mac.zip'
            name_templates = {'chrome-mac.zip': mac_name}
        elif os_type == 'linux':
            linux_x64_name = 'Linux_x64%2F{0}%2Fchrome-linux.zip'
            linux_x32_name = 'Linux%2F{0}%2Fchrome-linux.zip'
            name_templates = {'chrome-linux-x64.zip': linux_x64_name,
                              'chrome-linux-x32.zip': linux_x32_name}
        elif os_type == 'win64':
            win_x64_name = 'Win_x64%2F{0}%2Fchrome-win.zip'
            name_templates = {'chrome-win-x64.zip': win_x64_name}
            win64 = True
        else:
            win_x32_name = 'Win%2F{0}%2Fchrome-win32.zip'
            name_templates = {'chrome-win-x32.zip': win_x32_name}
            win = True

        # Prepare download
        value = {'version': version, 'position_url': position_url, 'position': position}
        status_codes = self.__get_chromium_download_url_core(name_templates, position, value, os_type, win, win64)
        check_status_code = all(status_code == 200 for status_code in status_codes)
        if check_status_code is False:
            for i in range(position - self.position_offset, position + self.position_offset + 1):
                if i <= position:
                    new_position = i + self.position_offset + 1
                else:
                    new_position = i - self.position_offset - 1
                status_codes = self.__get_chromium_download_url_core(name_templates,
                                                                     new_position,
                                                                     value,
                                                                     os_type,
                                                                     win,
                                                                     win64)
                check_status_code = all(status_code == 200 for status_code in status_codes)
                if check_status_code is True:
                    break

    def get_chromium_download_url(self, workers=10):
        """Function: chromium_download

        :param workers: how many concurrent requests to get the chromium url (default 3)
        """

        print('Info: Start to get chromium urls...')
        pool = ThreadPoolExecutor(max_workers=workers)
        futures = list()
        for os_type, values in self.chromium_positions.items():
            for value in values:
                version = value['version']
                position_url = value['position_url']
                position = value['position']
                future = pool.submit(self.__parallel_get_download_chromium_url,
                                     os_type=os_type,
                                     version=version,
                                     position_url=position_url,
                                     position=position)
                futures.append(future)
        pool.shutdown(wait=True)
        self.check_future_result(futures)

    def report(self):
        """Function: Report"""

        print('Info: Generating json/csv report...')

        # Json report
        json_report = 'chromium.stable.json'
        json_report_exists = os.path.exists(json_report)
        chromium_downloads = deepcopy(self.chromium_downloads)
        if json_report_exists is True:
            with open(json_report) as f:
                existed_chromium_downloads = json.loads(f.read())
                for os_type in self.os_type:
                    chromium_downloads[os_type] += existed_chromium_downloads[os_type]
        with open(json_report, 'w+') as f:
            json.dump(chromium_downloads, f, indent=4)

        # CSV report
        csv_report = 'chromium.stable.csv'
        csv_rows = list()
        for os_type, values in chromium_downloads.items():
            version = values['version']
            position_url = values['position_url']
            position = values['position']
            download_position = values['download_position']
            download_url = values['download_url']
            download_name = values['download_name']
            csv_row = [os_type, version, position_url, position, download_position, download_url, download_name]
            csv_rows.append(csv_row)
        with open(csv_report, 'w+') as f:
            csv_writer = csv.writer(f)
            csv_writer.writerows(csv_rows)

    def __chromium_download_core(self, os_type, version, download_url, download_name):
        """Private Function: __chromium_download_core"""

        cur_dir = os.getcwd()
        chromium_save_dir = os.path.join(cur_dir, 'Downloads', os_type, version)
        chromium_save_dir_exist_status = os.path.exists(chromium_save_dir)
        if chromium_save_dir_exist_status is False:
            os.makedirs(chromium_save_dir)
        chromium_file_path = os.path.join(chromium_save_dir, download_name)
        print('Info: Starting downloading {0}...'.format(chromium_file_path))
        try:
            with self.session.get(download_url, stream=True) as r:
                with open(chromium_file_path, 'wb') as f:
                    shutil.copyfileobj(r.raw, f)
        except (requests.RequestException,
                requests.exceptions.SSLError,
                requests.packages.urllib3.exceptions.SSLError) as e:
            error_message = 'Error: Unexpected error ' \
                            'when requesting download url: {0}, {1}'.format(download_url, e)
            print(Fore.RED + error_message)

    def chromium_download(self, workers=10):
        """Function: chromium_download

        :param workers: how many concurrent requests to download chromium (default 3)
        """

        # Only for test purpose
        # self.os_type = ['linux']
        # self.chromium_downloads = {
        #     'linux': [
        #         {
        #             'version': '44.0.2403.157',
        #             'position_url': 'https://omahaproxy.appspot.com/deps.json?version=44.0.2403.157',
        #             'position': 330231,
        #             'download_position': 330234,
        #             'download_url': 'https://www.googleapis.com/download/storage/v1/b/chromium-browser-snapshots/o/'
        #                             'Linux_x64%2F330234%2Fchrome-linux.zip?alt=media',
        #             'download_name': 'chrome-linux.zip'
        #         }
        #     ]
        # }

        print('Info: Start to download chromium...')
        pool = ThreadPoolExecutor(max_workers=workers)
        futures = list()
        for os_type, values in self.chromium_downloads.items():
            for value in values:
                version = value['version']
                download_url = value['download_url']
                download_name = value['download_name']
                future = pool.submit(self.__chromium_download_core,
                                     os_type=os_type,
                                     version=version,
                                     download_url=download_url,
                                     download_name=download_name)
                futures.append(future)
        pool.shutdown(wait=True)
        self.check_future_result(futures)


if __name__ == '__main__':
    chromium = Chromium()
    chromium.get_chromium_versions()
    chromium.prepare_chromium_position_urls()
    chromium.get_chromium_positions()
    chromium.get_chromium_download_url()
    chromium.report()
    # Download takes time, and not necessary to download all to git
    # Find the chromium.json, chromium.csv to get all download links
    # chromium.chromium_download()
