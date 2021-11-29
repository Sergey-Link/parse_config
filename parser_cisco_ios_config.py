#!/usr/bin/env python
from ciscoconfparse import CiscoConfParse
import ipaddress as ip
import sys
import json
import csv
import argparse
#import pandas as pd


description = """
Парсит конфигурцию cisco ios на выходе csv файл с vrf и csv файл с префиксами.
"""

aparser = argparse.ArgumentParser(description=description)
aparser.add_argument('-f', dest='config_file', help='Имя файла конфигурции', required = True)
aparser.add_argument('-s', dest='site', help='Название сайта. По умолчанию: "test site"', required=False, default = 'test site')
aparser.add_argument('-t', dest='tenant', help='Название тенанта. По умолчанию: "Управление эксплуатации ЛВС"', required=False, default = 'Управление эксплуатации ЛВС')
aparser.add_argument('-v', dest='config_type', help='Тип файла: ios or nxos. Пока только ios. Default: ios', required=False, default='ios')
aparser.add_argument('-o', dest='output_file', help='Имя файла csv', required=True)
args = aparser.parse_args()

#Ввод основных переменных

SITE = args.site
TENANT = args.tenant
PREF_ROLES = ['Users', 'Production']
FILE_CONFIG = args.config_file
#FILE_CONFIG = 'Bekasovo.cfg'
CONFIG_TYPE = args.config_type
#FILE_VRFS_JSON = 'vrfs_'+args.output_file+'.json'
FILE_VRFS_CSV = 'vrfs_'+args.output_file+'.csv'
#FILE_PREFIX_JSON = 'ip_prefix_'+args.output_file+'.json'
FILE_PREFIX_CSV = 'ip_prefix_'+args.output_file+'.csv'


parse = CiscoConfParse(FILE_CONFIG, syntax=CONFIG_TYPE)

#
#Получение списка vrf и запись его в словарь vrfs = {'vrf_name':'rd'}
#

vrfs = {}

#Получение списка vrf для конфигурации вида: "ip vrf vrf_name"

for vrf_obj in parse.find_objects('^ip\svrf\s'):
    vrf_name = vrf_obj.re_match_typed('^ip\svrf\s+(\S.+?)$')
    vrf_rd = vrf_obj.re_match_iter_typed(r'rd\s+(\S.+?)$')
    vrfs[vrf_name] = vrf_rd

#Получение списка vrf для конфигурации вида: "vrf definition vrf_name"

for vrf_obj in parse.find_objects('^vrf\sdefinition\s'):
    vrf_name = vrf_obj.re_match_typed('vrf\sdefinition\s+(\S.+?)$')
    vrf_rd = vrf_obj.re_match_iter_typed(r'rd\s+(\S.+?)$')
    vrfs[vrf_name] = vrf_rd
#
#Получение списка vlan и запись его в словарь vlans = {'vlan_id':'vlan_name'}
#

vlans = {}

for vlan_obj in parse.find_objects('^vlan\s'):
    vlan_id = vlan_obj.re_match_typed('^vlan\s+(\d{0,5}.+?)$')
    vlan_name = vlan_obj.re_match_iter_typed(r'name\s+(\S.+?)$')
    vlan_desc = vlan_obj.re_match_iter_typed(r'description\s+(\S.+?)$')
    if vlan_name and vlan_id[0].isdigit():
        vlans[vlan_id.strip()] = vlan_name
    else:
        if '-' in vlan_id:
            for k in range(int(vlan_id.split('-')[0]),int(vlan_id.split('-')[1])+1):
                vlans[str(k)] = 'Vlan'+str(k)
        else:
            if vlan_id[0].isdigit():
                vlans[vlan_id.strip()] = 'Vlan'+vlan_id.strip()

#
#Получение списка prefix и запись его в список
#
#        pref['prefix'] = intf_ip_network/mask_CIDR
#        pref['status'] = 'active'
#        pref['vrf'] = intf_vrf
#        pref['role'] = 'Users' or 'Production'
#        pref['description'] = interface description
#        pref['cf_Default_gateway'] = 'if mask < 29 intf_ip_address'
#        pref['cf_dhcp_managed'] = True if is ip helper
#        pref['vlan_vid'] = vlan_id
#        pref['vlan_name'] = vlan_name
#        pref['vlan_description'] = 'vlan_desc'
#        pref['site'] = SITE
#        pref['tenant'] = TENANT

ip_prefix = []


for intf_obj in parse.find_objects('^interface Vlan'):
    pref = {}
    intf_name = intf_obj.re_match_typed('^interface\s+(\S.+?)$')
    # Search children of all interfaces for a regex match and return
    # the value matched in regex match group 1.  If there is no match,
    # return a default value: ''
    intf_vrf_old = intf_obj.re_match_iter_typed(r'ip\svrf\sforwarding\s+(\S.+?)$')
    intf_vrf_new = intf_obj.re_match_iter_typed(r'vrf\sforwarding\s+(\S.+?)$')
    intf_ip_addr = intf_obj.re_match_iter_typed(
        r'ip\saddress\s(\d+\.\d+\.\d+\.\d+\s\d+\.\d+\.\d+\.\d+)', result_type=str,
        group=1, default='')
    intf_ip_helper = intf_obj.re_match_iter_typed(
        r'ip\shelper-address\s(\S.+?)$', result_type=str,
        group=1, default='')
    intf_desc = intf_obj.re_match_iter_typed(r'description\s+(\S.+?)$', result_type=str, default='', group=1)
    intf_shut = intf_obj.re_match_iter_typed(r'shutdown$', result_type=str, default='', group=0)

    if intf_ip_addr != '' and 'shutdown' not in intf_shut:
        pref['prefix'] = format(ip.IPv4Interface(intf_ip_addr.replace(' ','/')).network)
        pref['status'] = 'active'
        pref['vrf'] = intf_vrf_old
        pref['vrf'] = intf_vrf_new
        if ip.IPv4Interface(intf_ip_addr.replace(' ','/'))._prefixlen < 29:
            pref['role'] = PREF_ROLES[0]
        else:
            pref['role'] = PREF_ROLES[1]
        pref['description'] = intf_desc
        if ip.IPv4Interface(intf_ip_addr.replace(' ','/'))._prefixlen < 29:
            pref['cf_Default_gateway'] = format(ip.IPv4Interface(intf_ip_addr.replace(' ','/')).ip)
        else:
            pref['cf_Default_gateway'] = ''
        if intf_ip_helper:
            pref['cf_dhcp_managed'] = True
        else:
            pref['cf_dhcp_managed'] = False
        pref['vlan_vid'] = intf_name[4:]
        pref['vlan_name'] = vlans[intf_name[4:]]
        pref['vlan_description'] = 'vlan_desc'
        pref['site'] = SITE
        pref['tenant'] = TENANT

        ip_prefix.append(pref.copy())
#
#Запись файлов vrf-ов и ip prexffix
#

#Формирование списка врф-ов для записи в формате json:

vrfs_list = []
for name,rd in vrfs.items():
    vrf = {}
    vrf['name'] = name
    vrf['rd'] = rd
    vrfs_list.append(vrf)

#Запись файла с врф-ами json и csv:

#vrfs_json = json.dumps(vrfs_list, ensure_ascii=False)

#with open(FILE_VRFS_JSON, 'w', encoding='utf-8') as f:
#    f.write(vrfs_json)
if vrfs_list:
    with open(FILE_VRFS_CSV, 'w', newline='') as csvfile:
        csvwriter = csv.writer(csvfile, delimiter=',')
        csvwriter.writerow(vrfs_list[0].keys())
        for line in vrfs_list:
            csvwriter.writerow(line.values())


#data_json = pd.read_json(FILE_VRFS_JSON)

#data_json.to_csv(FILE_VRFS_CSV)

#Запись файла с префиксами-ами json и csv:

#ip_prefix_json = json.dumps(ip_prefix, ensure_ascii=False)

#with open(FILE_PREFIX_JSON, 'w', encoding='utf-8') as f:
#    f.write(ip_prefix_json)


with open(FILE_PREFIX_CSV, 'w', newline='') as csvfile:
    csvwriter = csv.writer(csvfile, delimiter=',')
    csvwriter.writerow(ip_prefix[0].keys())
    for line in ip_prefix:
        csvwriter.writerow(line.values())

#data_json = pd.read_json(FILE_PREFIX_JSON)

#data_json.to_csv(FILE_PREFIX_CSV)
# End of Script
