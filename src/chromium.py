from requests.packages.urllib3.util.retry import Retry
from concurrent.futures import ThreadPoolExecutor
from requests.adapters import HTTPAdapter
from os.path import dirname, abspath
from collections import OrderedDict
from colorama import Fore, init
from copy import deepcopy
import traceback
import requests
import argparse
import shutil
import time
import json
import sys
import csv
import os
import re

requests.packages.urllib3.disable_warnings()
init(autoreset=True)


class Chromium(object):
    """Download all the chromium old stable versions"""

    def __init__(self, channel='stable', fore_crawl=False):
        self.channel = channel
        self.force_crawl = self.validate_boole(fore_crawl)
        self.strip_chars = ' \r\n\t/"\',\\'
        self.os_type = {'mac': 'Mac/',
                        'win': 'Win/',
                        'win64': 'Win_x64/',
                        'linux': 'Linux/',
                        'linux64': 'Linux_x64/',
                        'android': 'Android/'}
        self.omahaproxy_host = 'https://omahaproxy.appspot.com'
        self.chromium_download_url_template = 'https://www.googleapis.com/download/storage/v1/b/' \
                                              'chromium-browser-snapshots/o/{0}?alt=media'
        self.chromium_prefix_url_template = 'https://www.googleapis.com/storage/v1/b/chromium-browser-snapshots/o?' \
                                            'delimiter=/&' \
                                            'prefix={0}&' \
                                            'fields=items(kind,mediaLink,metadata,name,size,updated),' \
                                            'kind,prefixes,nextPageToken'
        self.chromium_prefix_url_with_token_template = self.chromium_prefix_url_template + '&pageToken={1}'
        status_forcelist = [500, 502, 503, 504, 522, 524, 408, 400, 401, 403]
        retries = Retry(total=10, read=10, connect=10, backoff_factor=3, status_forcelist=status_forcelist)
        self.session = requests.session()
        self.session.mount('http://', HTTPAdapter(max_retries=retries))
        self.session.mount('https://', HTTPAdapter(max_retries=retries))
        self.session.verify = False
        self.chromium_versions = dict()
        self.chromium_position_urls = dict()
        self.chromium_positions = dict()
        self.chromium_downloads = dict()
        self.time_out = 300
        self.position_offset = 100
        self.chromium_existed_positions = dict()

    @staticmethod
    def validate_boole(target):
        """Function: validate boole"""

        target = str(target).lower()
        if target != 'true' and target != 'false':
            raise Exception('Error: The expected input for {0} should be: True or False'.format(target))
        if target == 'true':
            target = True
        else:
            target = False

        return target

    def __get_existed_positions_core(self, url, os_type, ini_start=False):
        """Private Function: __get_existed_positions_core"""

        try:
            res = self.session.get(url, timeout=self.time_out)
            status_code = res.status_code
            if status_code != 200:
                error_message = 'Fatal: Unexpected status code detected ' \
                                'when requesting prefix url: {0}, {1}'.format(status_code, url)
                print(Fore.YELLOW + error_message)
                sys.exit(1)
            content = json.loads(res.content)
            try:
                prefixes = content['prefixes']
            except KeyError:
                error_message = 'Fatal: Prefixes not in response: {0}, {1}'.format(url, content)
                print(Fore.YELLOW + error_message)
                sys.exit(1)
            prefixes_with_position = {re.search('/(.*?)/', prefix).group(1): prefix for prefix in prefixes}
            if ini_start is True:
                self.chromium_existed_positions[os_type] = prefixes_with_position
            else:
                self.chromium_existed_positions[os_type].update(prefixes_with_position)
            try:
                next_page_token = content['nextPageToken']
            except KeyError:
                next_page_token = None

            return next_page_token
        except (requests.RequestException,
                requests.exceptions.SSLError,
                requests.packages.urllib3.exceptions.SSLError) as e:
            error_message = 'Error: Unexpected error when requesting history url: {0}, {1}'.format(url, e)
            print(Fore.RED + error_message)

    def get_existed_positions(self):
        """Function: get_existed_positions

        Crawl all the existing positions by using the API:
        https://www.googleapis.com/storage/v1/b/chromium-browser-snapshots/o?
        delimiter=/&prefix=Mac/&fields=items(kind,mediaLink,metadata,name,size,updated),kind,prefixes,nextPageToken&
        pageToken=CgtNYWMvMTA1NDkzLw

        Note: Cannot use ThreadPoolExecutor to run parallel, because the api does not support
        """

        if len(self.chromium_versions) == 0:
            print('Info: No new stable release found for os type win/win64/mac/linux64/linux/android')
            return

        for os_type, prefix in self.os_type.items():
            print('Info: Get all the existed positions for {0}...'.format(os_type))
            url = self.chromium_prefix_url_template.format(prefix)
            next_page_token = self.__get_existed_positions_core(url, os_type, ini_start=True)
            while next_page_token is not None:
                url = self.chromium_prefix_url_with_token_template.format(prefix, next_page_token)
                next_page_token = self.__get_existed_positions_core(url, os_type)

    @staticmethod
    def check_future_result(futures):
        """Function: check_future_result"""

        for future in futures:
            try:
                future.result()
            except Exception as e:
                print(traceback.format_exc())
                raise Exception('Error: Exception found {0}'.format(e))

    def __process_difference(self, history_json_file, history_json_file_exists, releases):
        """Private Function: __process_difference"""

        if history_json_file_exists is False or self.force_crawl is True:
            return releases
        else:
            with open(history_json_file) as f:
                existed_release = json.loads(f.read())
            new_releases = [x for x in releases if x not in existed_release]
            return new_releases

    def get_chromium_versions(self):
        """Function: get_chromium_versions

        By take advantage of the api: https://omahaproxy.appspot.com/history.json?channel=stable&os=mac to get all the
        chromium release version
        available channel: stable, beta, dev, canary,
        available os: max, win, win64, android
        """

        print('Info: Start to get all chromium stable versions...')
        history_json_format = '{0}/history.json?channel={1}&os={2}'
        for os_type in self.os_type.keys():
            if os_type == 'linux64':
                url = history_json_format.format(self.omahaproxy_host, self.channel, 'linux')
            else:
                url = history_json_format.format(self.omahaproxy_host, self.channel, os_type)
            try:
                res = self.session.get(url, timeout=self.time_out)
                status_code = res.status_code
                content = res.content
                if status_code != 200:
                    error_message = 'Fatal: Unexpected status code ' \
                                    'when requesting history url: {0}, {1}'.format(status_code, url)
                    print(Fore.RED + error_message)
                    sys.exit(1)
                releases = json.loads(content)
                history_json_file = '{0}.history.json'.format(os_type)
                history_json_file_exists = os.path.exists(history_json_file)
                new_releases = self.__process_difference(history_json_file, history_json_file_exists, releases)
                if not new_releases:
                    print('Info: No new stable release found for os type {0}'.format(os_type))
                    continue
                with open(history_json_file, 'w+') as f:
                    json.dump(releases, f, indent=4)
                for release in new_releases:
                    try:
                        version = release['version']
                        self.chromium_versions.setdefault(os_type, {})[version] = list()
                    except KeyError:
                        pass
                for key in self.chromium_versions.keys():
                    print('get_chromium_versions: ', key, self.chromium_versions[key])
            except (requests.RequestException,
                    requests.exceptions.SSLError,
                    requests.packages.urllib3.exceptions.SSLError) as e:
                error_message = 'Error: Unexpected error when requesting history url: {0}, {1}'.format(url, e)
                print(Fore.RED + error_message)

    def prepare_chromium_position_urls(self):
        """Function: get_chromium_position_urls

        Prepare the url https://omahaproxy.appspot.com/deps.json?version=77.0.3865.120 to get the base position.
        """

        print('Info: Prepare the position urls...')
        deps_json_format = '{0}/deps.json?version={1}'
        for os_type, versions in self.chromium_versions.items():
            for version in versions.keys():
                url = deps_json_format.format(self.omahaproxy_host, version)
                value = {'position_url': url}
                self.chromium_position_urls.setdefault(os_type, {})[version] = value

    def __parallel_requests_to_get_positions(self, os_type, version, position_url, recursive=0):
        """Private Function: __parallel_requests_to_get_positions"""

        try:
            res = self.session.get(position_url, timeout=self.time_out)
            status_code = res.status_code
            content = res.content
            if status_code != 200:
                error_message = 'Error: Unexpected status code ' \
                                'when requesting position url: {0}, {1}'.format(status_code, position_url)
                print(Fore.YELLOW + error_message)
            else:
                try:
                    position_json = json.loads(content)
                    chromium_base_position = int(position_json['chromium_base_position'])
                    value = {'position_url': position_url, 'position': chromium_base_position}
                    self.chromium_positions.setdefault(os_type, {})[version] = value
                except (KeyError, TypeError, ValueError):
                    recursive += 1
                    if recursive > 3:
                        warning_message = 'Warning: chromium_base_position stills null, ' \
                                          'after tried 3 times {0}'.format(position_url)
                        print(Fore.YELLOW + warning_message)
                    else:
                        self.__parallel_requests_to_get_positions(os_type, version, position_url, recursive=recursive)
            time.sleep(5)
        except (requests.RequestException,
                requests.exceptions.SSLError,
                requests.packages.urllib3.exceptions.SSLError) as e:
            error_message = 'Error: Unexpected error when requesting position url: {0}, {1}'.format(position_url, e)
            print(Fore.RED + error_message)

    def get_chromium_positions(self, workers=3):
        """Function: get_chromium_positions

        Request the url https://omahaproxy.appspot.com/deps.json?version=77.0.3865.120 to get the base position.

        :param workers: concurrent requests to get the positions (default 3)
        """

        # # Only for test purpose
        # value = {
        #             'position_url': 'https://omahaproxy.appspot.com/deps.json?version=77.0.3865.120',
        #             'position': 681094
        # }
        # self.chromium_positions.setdefault('mac', {})['77.0.3865.120'].append(value)

        print('Info: Start to get all chromium positions...')
        pool = ThreadPoolExecutor(max_workers=workers)
        futures = list()
        for os_type, values in self.chromium_position_urls.items():
            for version, value in values.items():
                position_url = value['position_url']
                future = pool.submit(self.__parallel_requests_to_get_positions,
                                     os_type=os_type,
                                     version=version,
                                     position_url=position_url)
                futures.append(future)
        pool.shutdown(wait=True)
        self.check_future_result(futures)

        for key in self.chromium_positions.keys():
            print('get_chromium_positions: ', key, self.chromium_positions[key])

    def __get_download_url(self, os_type, version, position, value):
        """Private Function: get download url for chromium/chromium driver"""

        filter_strings = ['browser_tests', 'syms', 'shell', 'host', 'exe']
        prefix = self.chromium_existed_positions[os_type][position]
        url = self.chromium_prefix_url_template.format(prefix)
        res = self.session.get(url, timeout=self.time_out)
        status_code = res.status_code
        if status_code != 200:
            error_message = 'Error: Unexpected status code ' \
                            'when requesting prefix url: {0}, {1}'.format(status_code, url)
            print(Fore.RED + error_message)
        else:
            content = json.loads(res.content)
            try:
                items = content['items']
                items = [item for item in items
                         if all(filter_string not in item['name'] for filter_string in filter_strings)]
                sizes = [int(item['size']) for item in items]
                index = sizes.index(max(sizes))
                download_url = items[index]['mediaLink']
                try:
                    driver_download_url = [item['mediaLink'] for item in items if 'driver' in item['name']][0]
                except IndexError:
                    driver_download_url = 'Error: Cannot find the chrome driver in prefix, ' \
                                          'please check the download_prefix manually'
                value['download_position'] = int(position)
                value['download_prefix'] = url
                value['download_url'] = download_url
                value['driver_download_url'] = driver_download_url
                self.chromium_downloads.setdefault(os_type, {})[version] = value
            except KeyError:
                error_message = 'Error: Failed to get the download url from prefix: {0}'.format(url)
                print(Fore.RED + error_message)

    def __parallel_get_download_chromium_url(self, os_type, version, value, position):
        """Private Function: __parallel_requests_to_download_chromium"""

        existed_positions_by_os_type = self.chromium_existed_positions[os_type].keys()
        if str(position) in existed_positions_by_os_type:
            self.__get_download_url(os_type, version, str(position), value)
        else:
            for i in range(1, self.position_offset+1):
                new_position_right = str(position + i)
                new_position_left = str(position - i)
                if new_position_right in existed_positions_by_os_type:
                    self.__get_download_url(os_type, version, new_position_right, value)
                    break
                if new_position_left in existed_positions_by_os_type:
                    self.__get_download_url(os_type, version, new_position_left, value)
                    break
                if i == self.position_offset:
                    position_range = '[{0}, {1}]'.format(new_position_left, new_position_right)
                    error_message = 'Error: For {0}, failed to find working position in: {1}'.format(os_type,
                                                                                                     position_range)
                    value['download_position'] = position
                    value['download_prefix'] = error_message
                    value['download_url'] = error_message
                    value['driver_download_url'] = error_message
                    self.chromium_downloads.setdefault(os_type, {})[version] = value
                    break

    def get_chromium_download_url(self, workers=100):
        """Function: chromium_download

        Use https://www.googleapis.com/storage/v1/b/chromium-browser-snapshots/o?
        delimiter=/&
        prefix=Mac/681090/&
        fields=items(kind,mediaLink,metadata,name,size,updated),kind,prefixes,nextPageToken

        :param workers: how many concurrent requests to get the chromium url (default 3)
        """

        print('Info: Start to get chromium urls...')
        pool = ThreadPoolExecutor(max_workers=workers)
        futures = list()
        for os_type, values in self.chromium_positions.items():
            for version, value in values.items():
                position_url = value['position_url']
                position = value['position']
                value = {'position_url': position_url, 'position': position}
                future = pool.submit(self.__parallel_get_download_chromium_url,
                                     os_type=os_type,
                                     version=version,
                                     value=value,
                                     position=position)
                futures.append(future)
        pool.shutdown(wait=True)
        self.check_future_result(futures)

    def __make_up_missing_points(self, current_json):
        """Private function: __make_up_missing_points
        What is the issue:
        Because of the Google API is not stable, sometimes, we could not get the chromium position

        For example:
        1) The API could be 502 error: https://omahaproxy.appspot.com/deps.json?version=37.0.2062.120
        2) The "chromium_base_position" in response data from above API could be "unknown"
        3) Failed to find the position between [position-100, position+100] (cannot fix)
          seems a google bug, some version's position is strange, for example:
          Strange: the 115.0.5790.110 position is 1583, but 114.0.5735.91 position is 1135570
          OS: win64
          Chrome Version: 115.0.5790.110, 114.0.5735.91
          Position URL: https://omahaproxy.appspot.com/deps.json?version=115.0.5790.110
                        https://omahaproxy.appspot.com/deps.json?version=114.0.5735.91
          Position: 1583, 1135570

        How to avoid:
        Compare the current json result with existing master branch json result as bellow
        Find the points that are not in current json, but in master json
        And then make the missing points into current json
        https://raw.githubusercontent.com/Bugazelle/chromium-all-old-stable-versions/master/chromium.stable.json
        """

        master_json_url = 'https://raw.githubusercontent.com/Bugazelle/chromium-all-old-stable-versions' \
                          '/master/chromium.stable.json'
        res = self.session.get(master_json_url, timeout=self.time_out)
        master_json = res.json()
        master_versions = {k: v.keys() for k, v in master_json.items()}
        current_versions = {k: v.keys() for k, v in current_json.items()}

        for k in master_versions.keys():
            master_version_list = master_versions[k]
            current_version_list = current_versions[k]

            in_master_not_in_current = list(set(master_version_list).difference(set(current_version_list)))
            diff_count = len(in_master_not_in_current)
            warning_message = 'Warning: chrome version in master_json_url {3} \n' \
                              'but not in current crawled json (already fixed): \n' \
                              'OS Type: {0} \n' \
                              'Diff Count: {1} \n' \
                              'In master_json_url but not in current crawled json: {2}'\
                .format(k, diff_count, in_master_not_in_current, master_json_url)
            if diff_count > 0:
                print('*' * 100)
                print(Fore.YELLOW + warning_message)
            for version in in_master_not_in_current:
                current_json[k][version] = master_json[k][version]

        return current_json

    def report(self):
        """Function: Report"""

        print('Info: Generating json/csv report...')

        # Json report
        key_list = ['position', 'download_position', 'download_prefix', 'position_url', 'download_url',
                    'driver_download_url']
        parent_dir = dirname(dirname(abspath(__file__)))
        json_report = os.path.join(parent_dir, 'chromium.stable.json')
        json_report_exists = os.path.exists(json_report)
        chromium_downloads = deepcopy(self.chromium_downloads)
        if json_report_exists is True and self.force_crawl is False:
            with open(json_report) as f:
                existed_chromium_downloads = json.loads(f.read())
                for os_type in self.os_type.keys():
                    try:
                        chromium_downloads[os_type].update(existed_chromium_downloads[os_type])
                    except KeyError:
                        chromium_downloads[os_type] = dict()
                        chromium_downloads[os_type].update(existed_chromium_downloads[os_type])

        # Make up the missing points
        chromium_downloads = self.__make_up_missing_points(current_json=chromium_downloads)

        # Generate the json file
        sorted_chromium_downloads = dict()
        for k in chromium_downloads.keys():
            points = chromium_downloads[k]
            sorted_points = OrderedDict(sorted(points.items(), key=lambda t: int(t[0].split('.')[0]), reverse=True))
            for version in sorted_points.keys():
                download_details = sorted_points[version]
                sorted_points[version] = OrderedDict((k, download_details[k]) for k in key_list)
            sorted_chromium_downloads[k] = sorted_points
        with open(json_report, 'w+') as f:
            json.dump(sorted_chromium_downloads, f, indent=4)

        # CSV report
        csv_report = os.path.join(parent_dir, 'chromium.stable.csv')
        csv_rows = list()
        headers = ['os', 'version', 'position_url', 'position', 'download_position', 'download_prefix', 'download_url',
                   'driver_download_url']
        csv_rows.append(headers)
        for os_type, values in sorted_chromium_downloads.items():
            for version, value in values.items():
                position_url = value['position_url']
                position = value['position']
                download_position = value['download_position']
                download_prefix = value['download_prefix']
                download_url = value['download_url']
                driver_download_url = value['driver_download_url']
                csv_row = [os_type, version, position_url, position, download_position, download_prefix, download_url,
                           driver_download_url]
                csv_rows.append(csv_row)
        with open(csv_report, 'w+') as f:
            csv_writer = csv.writer(f)
            csv_writer.writerows(csv_rows)

    def __chromium_download_core(self, os_type, version, download_url):
        """Private Function: __chromium_download_core"""

        cur_dir = os.getcwd()
        chromium_save_dir = os.path.join(cur_dir, 'Downloads', os_type, version)
        chromium_save_dir_exist_status = os.path.exists(chromium_save_dir)
        if chromium_save_dir_exist_status is False:
            os.makedirs(chromium_save_dir)
        chromium_file_path = os.path.join(chromium_save_dir, 'chrome.zip')
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

        # # Only for test purpose
        # self.os_type = ['linux']
        # self.chromium_downloads = {
        #     'linux': {
        #         '44.0.2403.157': {
        #             'position_url': 'https://omahaproxy.appspot.com/deps.json?version=44.0.2403.157',
        #             'position': 330231,
        #             'download_position': 330234,
        #             'download_url': 'https://www.googleapis.com/download/storage/v1/b/chromium-browser-snapshots/o/'
        #                             'Linux_x64%2F330234%2Fchrome-linux.zip?alt=media'
        #         }
        #     }
        # }

        print('Info: Start to download chromium...')
        pool = ThreadPoolExecutor(max_workers=workers)
        futures = list()
        for os_type, values in self.chromium_downloads.items():
            for version, value in values.items():
                download_url = value['download_url']
                future = pool.submit(self.__chromium_download_core,
                                     os_type=os_type,
                                     version=version,
                                     download_url=download_url)
                futures.append(future)
        pool.shutdown(wait=True)
        self.check_future_result(futures)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Crawl the chromium...')
    parser.add_argument('-f', '--force', nargs='?', default=False, const=False,
                        help='Force crawl all. Default: False')
    args = parser.parse_args()
    chromium = Chromium(fore_crawl=args.force)
    chromium.get_chromium_versions()
    chromium.get_existed_positions()
    chromium.prepare_chromium_position_urls()
    chromium.get_chromium_positions()
    chromium.get_chromium_download_url()
    chromium.report()
    # Download takes time, and not necessary to download all to git
    # Find the chromium.stable.json, chromium.stable.csv to get all download links
    # chromium.chromium_download()
