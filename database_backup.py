#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File  : database_backup.py
# @Author: bjxing
# @Date  : 2024/01/09
# @Desc  : 备份类

import os
import pymysql
import time
import pymongo
import bisect
import subprocess
import math
import socket
from configparser import ConfigParser
from datetime import datetime
from os import path
from sshtunnel import SSHTunnelForwarder
from args_parser import get_config_file

config_file = get_config_file()
config = ConfigParser()
cfg = config.read(config_file, encoding='utf-8')


class UnsupportedMongoDBVersionError(Exception):
    def __init__(self, message="Unsupported MongoDB version"):
        self.message = message
        super().__init__(self.message)


class DatabaseBackup(object):
    def __init__(self, section, logger):
        self.logger = logger.debug
        self.mongo_dump_path = None
        self.mongo_project = config.get(section, 'project')
        self.mongo_host = config.get(section, 'host')
        self.mongo_port = config.get(section, 'port')
        self.mongo_user = config.get(section, 'user')
        self.mongo_password = config.get(section, 'password')
        self.mongo_databases = config.get(section, 'target_dbs').split(',')
        self.backup_directory = config.get('Default',
                                           'back_path') + self.mongo_host + ":" + self.mongo_port + '/' + time.strftime(
            "%Y%m%d")
        self.retention_time = int((config.get('Default', 'retention_time'))) * 24 * 60 * 60
        self.start_time = None
        self.end_time = None
        self.elapsed_time = None
        self.bksize = None
        self.bkstate = None
        self.proxy_host = config.get('Proxy_Server', 'proxy_host')
        self.proxy_port = config.get('Proxy_Server', 'proxy_port')
        self.proxy_username = config.get('Proxy_Server', 'proxy_username')
        self.proxy_password = config.get('Proxy_Server', 'proxy_password')
        self.report_host = config.get('Info_Reporting', 'host')
        self.report_port = config.get('Info_Reporting', 'port')
        self.report_user = config.get('Info_Reporting', 'user')
        self.report_password = config.get('Info_Reporting', 'password')
        self.version = None
        self.db_list = None

    def perform_backup(self, db_name):
        try:
            self.logger(f"开始执行备份任务: {db_name}")
            self.start_time = time.time()
            self.get_version()
            self.logger(f"查看当前数据库版本: v{self.version}")
            if 3 <= self.version < 4.2:
                self.mongo_dump_path = path.abspath(path.join(path.dirname(__file__), 'bin/4.0.2/mongodump'))
            elif 4.2 <= self.version <= 7.0:
                self.mongo_dump_path = path.abspath(path.join(path.dirname(__file__), 'bin/100.9.4/mongodump'))
            else:
                raise UnsupportedMongoDBVersionError()

            if not (os.path.exists(self.backup_directory)):
                os.makedirs(self.backup_directory)
                self.logger("备份目录不存在，创建目录" + self.backup_directory)
            backup_path = self.backup_directory + "/" + db_name + '_' + time.strftime("%Y%m%d%H%M%S")
            self.logger(f"正在连接数据库{self.mongo_host}:{self.mongo_port}，开始执行备份{db_name}")
            command = "%s -h %s:%s -u %s -p %s  --authenticationDatabase admin --gzip -d %s -o %s" % \
                      (self.mongo_dump_path, self.mongo_host, self.mongo_port, self.mongo_user, self.mongo_password,
                       db_name, backup_path)
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True,
                                    universal_newlines=True)
            self.logger(f"[{command}] 标准错误输出: {result.stderr}")
            if os.path.exists(backup_path):
                fsize = self.get_dir_size(backup_path)
                self.bksize = self.format_filesize(fsize)
                self.bkstate = 1
            else:
                self.bksize = "0B"
                self.bkstate = 0
        except (UnsupportedMongoDBVersionError, Exception) as e:
            if isinstance(e, UnsupportedMongoDBVersionError):
                self.logger(f"当前备份程序不支持{self.version}！")
            else:
                self.logger(f"执行失败: {str(e)}")
            self.bksize = 0
            self.bkstate = 0
            self.logger(f"***备份任务 {db_name} 执行失败!!!***")
        finally:
            self.end_time = time.time()
            self.elapsed_time = self.format_time(math.ceil(self.end_time - self.start_time))
            self.logger(f"备份任务 {db_name} 执行完毕，耗时: {self.elapsed_time},备份文件:{self.bksize}。")
            if int(config.get('Info_Reporting', 'report_enabled')) == 1:
                self.backup_info_reporting(db_name)
            else:
                self.logger(f"备份信息上报已被关闭，请在配置中开启。")
        return self.start_time, self.end_time, self.elapsed_time, self.bksize, self.bkstate

    def query_databases(self):
        try:
            client = pymongo.MongoClient(host=self.mongo_host, port=int(self.mongo_port),
                                         username=self.mongo_user, password=self.mongo_password)
            self.db_list = client.list_database_names()
        except Exception as e:
            self.logger("执行数据库查询出现异常：%s", str(e))
            self.db_list = ['ERROR']
        return self.db_list

    def get_version(self):
        client = pymongo.MongoClient(host=self.mongo_host, port=int(self.mongo_port),
                                     username=self.mongo_user, password=self.mongo_password)
        server_info = client.server_info()
        version = server_info.get('version')
        version_parts = version.split('.')
        major_version = int(version_parts[0])
        minor_version = int(version_parts[1])
        self.version = float(f"{major_version}.{minor_version}")
        return self.version

    def format_filesize(self, size):
        d = [(1024 - 1, 'K'), (1024 ** 2 - 1, 'M'), (1024 ** 3 - 1, 'G'), (1024 ** 4 - 1, 'T')]
        s = [x[0] for x in d]
        index = bisect.bisect_left(s, size) - 1
        if index == -1:
            return str(size) + 'B'
        else:
            b, u = d[index]
        return str(round(size / (b + 1), 1)) + u

    def format_time(self, size):
        d = [(60 - 1, '分钟'), (3600 - 1, '小时')]
        s = [x[0] for x in d]
        index = bisect.bisect_left(s, size) - 1
        if index == -1:
            return str(size) + '秒'
        else:
            b, u = d[index]
        return str(round(size / (b + 1), 1)) + u

    def get_dir_size(self, path):
        total_size = 0
        for root, dirs, files in os.walk(path):
            for file in files:
                file_path = os.path.join(root, file)
                total_size += os.path.getsize(file_path)
        return total_size

    def clean_old_backups(self, section):
        if not self.retention_time:
            self.logger(f"未设置备份保留时长，请手动回收备份文件。")
        else:
            del_time = time.strftime("%Y%m%d", time.gmtime(time.time() - self.retention_time))
            root_backup_directory = config.get('Default', 'back_path') + self.mongo_host + ":" + self.mongo_port + '/'
            for root, directories, files in os.walk(root_backup_directory):
                for directory in directories:
                    if directory < del_time:
                        directory_to_delete = root_backup_directory + directory
                        result = subprocess.run(['rm', '-rf', directory_to_delete], stdout=subprocess.PIPE,
                                                stderr=subprocess.PIPE, text=True)
                        if result.returncode == 0:
                            self.logger(
                                f"删除数据库{self.mongo_host}:{self.mongo_port}的备份文件{del_time}前的数据，文件{directory_to_delete}删除成功。")
                        else:
                            self.logger(
                                f"删除数据库{self.mongo_host}:{self.mongo_port}的备份文件{del_time}前的数据失败，标准错误：{result.stderr}")
                        # self.logger(f"删除数据库{self.mysql_host}:{self.mysql_port}的备份文件{del_time}前的数据，文件：{result.stdout}。")

    def backup_info_reporting(self, dbname):
        self.server = None
        self.db_host = None
        self.db_port = None
        try:
            max_retries = 3
            retry_count = 0
            connected = False
            while not connected and retry_count < max_retries:
                try:
                    if int(config.get('Proxy_Server', 'proxy_enabled')) == 1:
                        self.logger(f"已开启数据上报代理模式！")
                        self.server = SSHTunnelForwarder(
                            ssh_address_or_host=(self.proxy_host, int(self.proxy_port)),
                            ssh_username=self.proxy_username,
                            ssh_password=self.proxy_password,
                            remote_bind_address=(self.report_host, int(self.report_port)),
                            local_bind_address=('127.0.0.1', 0),
                        )
                        self.server.start()
                        self.server.check_tunnels()
                        # print(self.server.tunnel_is_up, flush=True)
                        if self.server.is_active:
                            connected = True
                            self.local_port = self.server.local_bind_port
                            self.logger(
                                '本地端口:{}已转发至远程端口{}:{}'.format(self.local_port, self.proxy_host, self.proxy_port))
                        else:
                            self.logger(
                                '本地端口{}:{}转发失败，请重试'.format(self.server.local_bind_host, self.server.local_bind_port))

                        self.db_host = self.server.local_bind_host  # server.local_bind_host 是 参数 local_bind_address 的 ip
                        self.db_port = self.server.local_bind_port  # server.local_bind_port 是 参数 local_bind_address 的 port
                    else:
                        self.logger(f"未开启数据上报代理模式！")
                        self.db_host = self.report_host
                        self.db_port = int(self.report_port)

                    conn = pymysql.connect(
                        host=self.db_host,
                        port=self.db_port,
                        user=self.report_user,
                        passwd=self.report_password,
                        db=config.get('Info_Reporting', 'db'),
                    )
                    insert_sql = "INSERT INTO dbs_backup_info(project, source, category, address, port, dbname, " \
                                 "bksize, bktype, bkstate, start_time, end_time, elapsed_time, bklocate) " \
                                 "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"

                    params = (self.mongo_project, 'IDC', 'MongoDb', self.mongo_host, self.mongo_port, dbname, self.bksize, '全量',
                              self.bkstate, self.convert_timestamp_to_datetime(self.start_time),
                              self.convert_timestamp_to_datetime(self.end_time), self.elapsed_time, self.get_local_ip())
                    cur = conn.cursor()
                    cur.execute(insert_sql, params)
                    conn.commit()
                    formatted_sql = cur.mogrify(insert_sql, params)
                    self.logger(f"执行数据上报{self.report_host}，插入语句： {formatted_sql}")
                    cur.close()
                    conn.close()
                    if connected:
                        self.server.stop()  # 连接成功后释放端口
                        self.logger(f"关闭代理通道。")
                except Exception as e:
                    self.logger(f"连接失败: {str(e)}")
                    retry_count += 1
                    self.logger(f"重试次数: {retry_count}")
                    time.sleep(5)  # 等待一段时间后重试
        except Exception as e:
            self.logger(f"备份信息上报时发生异常: {str(e)}")
            return 'failed'

    def convert_timestamp_to_datetime(self, timestamp):
        formatted_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        return formatted_time

    def get_local_ip(self):
        ip = socket.gethostbyname(socket.gethostname())
        return ip
