# Mongobackup

#### 介绍

主要使用mongodump实现批量的实例库进行备份，并支持数据上报。

```bash
1、支持批量实例备份 
2、实例多库时可以为空，自动查找实例中的库进行全备 
3、支持数据上报 
4、支持数据上报代理模式 
5、增加参数解释说明
```
#### 版本更新

v1.2.1
```bash
1、修复关闭代理模式后循环上报问题
2、取消错误后重试次数
```

v1.2.0
```bash
1、新增支持更多的mongodb版本，不仅限于4.0
2、修复备份失败后文件大小和备份状态为None的情况，赋予正确的状态
3、修复开始连接时报错不上报的问题，修复后会上报一个ERROR到上报表以便检查。
4、上报表中增加一个字段用于上报备份位置
5、修改使用本地动态端口进行透传代理，增加重试机制。

---增加备份位置字段
ALTER TABLE dbs_backup_info
ADD COLUMN bklocate varchar(32) CHARACTER SET utf8mb4;
```
#### 软件架构
软件使用python3编写，支持linux64下的版本:
MongoDB 7.0
MongoDB 6.0
MongoDB 5.0
MongoDB 4.4
MongoDB 4.2
MongoDB 4.0
MongoDB 3.6
MongoDB 3.2

#### 安装教程

1、创建信息上报库，如果关闭上报功能可不创建。

```bash
/* 创建信息上报库 */
DROP TABLE IF EXISTS `dbs_backup_info`;
CREATE TABLE `dbs_backup_info`  (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `project` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '项目名称',
  `source` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '来源',
  `category` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '数据库类型',
  `address` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '数据库地址',
  `port` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '数据库端口',
  `dbname` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '数据库名',
  `bksize` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '备份大小',
  `bktype` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '备份类型',
  `bkstate` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '备份状态',
  `start_time` timestamp(0) NOT NULL DEFAULT CURRENT_TIMESTAMP(0) COMMENT '开始时间',
  `end_time` timestamp(0) NULL DEFAULT NULL COMMENT '结束时间',
  `elapsed_time` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '持续时间',
  `bklocate` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL COMMENT '备份位置',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `start_time_index`(`start_time`) USING BTREE
) ENGINE = InnoDB
  AUTO_INCREMENT = 1
  CHARACTER SET = utf8mb4
  COLLATE = utf8mb4_general_ci
  ROW_FORMAT = Dynamic;

SET FOREIGN_KEY_CHECKS = 1;
```

2、创建上报库账号（可选）

```bash
/* 创建上报库账号*/
CREATE USER 'backup_reporting'@'%' IDENTIFIED BY 'password';
GRANT INSERT, UPDATE ON alart_history.dbs_backup_info TO 'backup_reporting'@'%';
FLUSH PRIVILEGES;
```

3、创建备份账号（可选）

```bash
/* 创建备份账号*/
use admin
db.createUser({
  user: "backup",
  pwd: "password",
  roles: [{ role: "backup", db: "admin" }]
})
```

4、修改配置

config.ini中修改配置，多实例备份复制[DB1]配置，以DB开始，如DB1...DB10等

#### 使用说明
手动执行备份
  
可以根据需求使用解释器运行，或者使用版本发布中打包后的可执行文件运行
  
1、使用python3解释器运行
```bash
pip3 install -r requirements.txt 
python3 main.py
```

2、使用版本发布中可执行文件运行
```bash
chmod +x mongobackup 
./mongobackup
```

定时执行备份

例如： 每日一点进行备份 
```bash
crontab -e 
0 1 * * * cd /data/scripts/mongo_backup/&&./mongobackup
```


#### 参数
```bash
-v 查看版本信息
-c 指定配置文件
```