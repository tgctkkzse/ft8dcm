#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import threading
import time
from socket import socket, AF_INET, SOCK_DGRAM, SOCK_STREAM
import select
import subprocess
import json
from datetime import datetime, timedelta, timezone
import requests
from requests.exceptions import Timeout
import xml.etree.ElementTree as ET

import wx

import adif_io
from ft8slack import ft8slack
from PacketReader import PacketReader

class ft8dc:
    def __init__(self,frm):
        self.frm = frm

        self.Receiving = False
        self.cq_lists = []
        self.call_lists = []
        self.country_lists = []
        self.details_lists = []
        self.grid_lists = []
        self.dial_frequency_s = ''
        self.freq_n = ''
        self.band_n = ''
        self.band_b = ''
        self.tx_mode = ''
        self.rx_df = 0
        self.tx_df = 0

        self.slack_api_token = 'sloack token'
        self.channel_id_ham = "C07NBH1SAQ5"
        self.channel_id_logged = "C07P3Q86CRW"
        self.ft8slack = ft8slack(self.slack_api_token)
        
    def SetReceiving(self,mode):
        self.Receiving = mode

    def GetReceiving(self):
        return self.Receiving

    def call_lists_append(self,call,country,details,grid):
        self.call_lists.append(call)
        self.country_lists.append(country)
        self.details_lists.append(details)
        self.grid_lists.append(grid)
        return len(self.call_lists)-1

    def call_lists_find(self,call):
        if call in self.call_lists:
            return self.call_lists.index(call)
        else:
            return -1

    def call_lists_get(self,no):
        return  self.call_lists[no],self.country_lists[no],self.details_lists[no],self.grid_lists[no]

    def call_lists_set(self,call,country,details,grid):
        self.cl = self.call_lists_find(call)
        if self.cl < 0:
            self.url = 'https://www.hamqth.com/dxcc.php?callsign='+call
            try:
                self.rdxcc = requests.get(self.url, timeout=1)
                self.dxcc = ET.fromstring(self.rdxcc.text)
                self.country = self.dxcc.find('{http://www.hamqth.com}dxcc/{http://www.hamqth.com}name').text
                self.details = self.dxcc.find('{http://www.hamqth.com}dxcc/{http://www.hamqth.com}details').text
                self.call_lists_append(call,self.country,self.details,grid)
            except Timeout:
                print("Timeout: {}".format(self.url));
            except Exception as e:
                print("DXCC Error: {}".format(e));
                print("URL: {}".format(self.url));
                print("res: {}".format(self.rdxcc));

            if (self.country == 'Japan') and (len(self.call)>=5):
                try:
                    self.url = '-H "user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36" "https://www.tele.soumu.go.jp/musen/list?ST=1&OF=2&DA=1&OW=AT&SK=2&DC=1&SC=1&MA='+call+'"'
                    self.command = 'curl -s -o soumuresult.txt ' + self.url
                    self.ret = subprocess.run(self.command, shell=True, encoding='utf-8', stdout=subprocess.PIPE)
                    with open('soumuresult.txt', 'r', encoding='utf-8') as f:
                        self.soumuresult = json.load(f)
                    if 'musen' in self.soumuresult:
                        radioSpec1 = self.soumuresult['musen'][0]['detailInfo']['radioSpec1']
                        if int(self.soumuresult['musenInformation']['totalCount']) > 1:
                            if radioSpec1 > self.soumuresult['musen'][1]['detailInfo']['radioSpec1']:
                                radioSpec1 = self.soumuresult['musen'][1]['detailInfo']['radioSpec1']
                        self.details = self.soumuresult['musen'][0]['listInfo']['tdfkCd'] + ', ' + radioSpec1
                        self.details_lists[len(self.details_lists)-1] = self.details
                except Exception as e:
                    print("error: {}".format(e));
            self.grid = grid
        else:
            wcall,self.country,self.details,wgrid = self.call_lists_get(self.cl)
            try:
                if len(grid) <=0:
                    self.grid = wgrid
            except Exception as e:
                print("error: {}".format(e));
        return call,self.country,self.details,self.grid

    def ExecRecv(self, ip, num, adif_path):
        self.ip = ip
        self.num = num
        self.adif_path = adif_path
        self.th = threading.Thread(target=self.ServThread, daemon=True)
        self.th.start()
        return

    def DCMessage0(self, ps):
        self.client_id = ps.QString()
        self.max_schema = ps.QInt32()
        self.version = ps.QString()
        self.revision = ps.QString()

#        out = "Hertbeat: %s %s %s %s %s %s %d %d" % (client_id,version,revision,self.dial_frequency_s,self.band_n,self.tx_mode,self.rx_df,self.tx_df)
#        out3 = out
        if self.band_b != self.band_n:
            self.cq_lists = []
            self.c_cq_lists = 1
            self.band_b = self.band_n
        else:
            for i in range(len(self.cq_lists)):
                if (self.nowut-self.cq_lists[i][9]) >= (5*60):
                    del self.cq_lists[i]
                    self.c_cq_lists = 1
                    break
                
    def DCMessage1(self, ps):
        self.client_id = ps.QString()
        self.dial_frequency = ps.QInt64()
        self.dial_frequency_s,self.band_n = ps.getDialFrequency(self.dial_frequency)
        self.mode = ps.QString()
        self.dx_call = ps.QString()
        self.report = ps.QString()
        self.tx_mode = ps.QString()
        self.tx_enabled = ps.QInt8()
        self.transmitting = ps.QInt8()
        self.decoding = ps.QInt8()
        self.rx_df = ps.QInt32()
        self.tx_df = ps.QInt32()
        self.de_call = ps.QString()
        self.de_grid = ps.QString()
        self.dx_grid = ps.QString()
        self.tx_watchdog = ps.QInt8()
        self.sub_mode = ps.QString()
        self.fast_mode = ps.QInt8()
        self.special_op_mode = ps.QInt8()

#        out3 = "Status: %s %s %s %s %s %s %d %d %d %d %d %s %s %s %d %s %d %d" %\
#                      (client_id,dial_frequency_s,mode\
#                      ,dx_call,report,tx_mode,tx_enabled,transmitting,decoding,rx_df,tx_df\
#                      ,de_call,de_grid,dx_grid,tx_watchdog,sub_mode,fast_mode,special_op_mode\
#                      )
#        send_slack_message(out3,channel_id_ham)
        if self.transmitting == 1:
#            s_nowut = nowut
            for i in range(len(self.cq_lists)):
                if self.cq_lists[i][2] == 'S':
                    self.cq_lists[i][2] = ' '
                    self.c_cq_lists = 1
            self.cq_list = []
            self.stat = 'S'
            self.call = self.dx_call
            self.grid = self.dx_grid
            self.country = ''
            self.details = ''
            if self.call.find('/') == -1:
                self.call_lists_set(self.call,self.country,self.details,self.grid)

                self.cq_list = [self.call,self.grid,self.stat,0,self.freq_n,self.band_n,self.tx_mode,self.country,self.details,self.nowut]
                for i in range(len(self.cq_lists)):
                    if self.cq_lists[i][0] == self.call:
                        self.cq_list[3] = self.cq_lists[i][3]
                        del self.cq_lists[i]
                        break
                self.cq_lists.insert(0,self.cq_list)
                self.c_cq_lists = 1
        elif self.tx_enabled == 0:
            for i in range(len(self.cq_lists)):
                if self.cq_lists[i][2] == 'S':
                        self.cq_lists[i][2] = ' '
                        self.c_cq_lists = 1

        self.HeadSetLabel()

    def DCMessage2(self, ps):
        self.client_id = ps.QString()
        self.new_decode = ps.QInt8()
        self.millis_since_midnight = ps.QInt32()
        self.DiffTime = ps.getDiffTime(self.millis_since_midnight)
        self.snr = ps.QInt32()
        self.delta_time = ps.QFloat()
        self.delta_frequency = ps.QInt32()
        self.mode = ps.QString()
        self.message = ps.QString()
        self.low_confidence = ps.QInt8()
        self.off_air = ps.QInt8()

#        out = "Decode: %s %d %s %3d %4.1f %4d %s %s %d %d" %\
#        (client_id,new_decode,DiffTime,snr\
#        ,delta_time\
#        ,delta_frequency\
#        ,mode,message,low_confidence,off_air
#        )
        if type(self.message) is str:
            if 'JL1RSH' in self.message:
                self.ft8slack.send_slack_message(self.message,self.channel_id_ham)
        else:
            self.message = ''
        self.msg = self.message.split()
    
        self.cq_list = []
        self.stat = ' '
        self.call = ''
        self.grid = ''
        self.country = ''
        self.details = ''
        if len(self.msg) >= 2:
            if self.msg[0] == 'CQ':
                if len(self.msg) >= 4:
                    if self.msg[1] == 'JA':
                        self.stat = ' '
                    elif self.msg[1] == 'AS':
                        self.stat = ' '
                    elif self.msg[1] == 'QRP':
                        self.stat = ' '
                    elif self.msg[1] == 'POTA':
                        self.stat = ' '
                    else:
                        self.stat = 'D'
                    self.call = self.msg[2]
                    self.grid = self.msg[3]
                elif len(self.msg) == 3:
                    if (len(self.msg[1]) <= 2) or (len(self.msg[2]) != 4):
                        self.stat = 'D'
                        self.call = self.msg[2]
                        self.grid = ''
                    else:
                        self.stat = ' '
                        self.call = self.msg[1]
                        self.grid = self.msg[2]
                else:
                    self.stat = ' '
                    self.call = self.msg[1]
                    self.grid = '    '

                if self.call.find('/') == -1:
                    self.call_lists_set(self.call,self.country,self.details,self.grid)
      
                    if len(self.msg) >= 4:
                        if self.msg[1] == 'DX':
                            if self.country == 'Japan':
                                self.stat = 'D'
                            else:
                                self.stat = ' '

                self.value = next((d["CALL"] for d in self.qsos_raw if (d["CALL"] == self.call and d["MODE"] == self.tx_mode and d["BAND"] == self.band_n)), None)
#                print("%s %s %s: %s" % (self.call,self.tx_mode,self.band_n,self.value))
                if self.value == self.call:
                    self.stat = 'X'
                self.cq_list = [self.call,self.grid,self.stat,self.snr,self.freq_n,self.band_n,self.tx_mode,self.country,self.details,self.nowut]
                a_flag = 0
                for i in range(len(self.cq_lists)):
                    if self.cq_lists[i][0] == self.call:
                        if self.stat == 'X' or self.stat == 'D':
                            self.cq_lists[i][2] = self.stat
                            self.cq_lists[i][3] = self.snr
                            a_flag = 1
                            self.c_cq_lists = 1
                        else:
                            del self.cq_lists[i]
                        break
                if a_flag == 0:
                    if self.stat == 'X' or self.stat == 'D':
                        self.cq_lists.append(self.cq_list)
                    else:
                        self.cq_lists.insert(0,self.cq_list)
                    self.c_cq_lists = 1
            else:
                if len(self.msg) == 3:
                    self.call = self.msg[1]
                    self.stat = ' '
                    self.value = next((d["CALL"] for d in self.qsos_raw if (d["CALL"] == self.call and d["MODE"] == self.tx_mode and d["BAND"] == self.band_n)), None)
#                    print("%s %s %s: %s" % (self.call,self.tx_mode,self.band_n,self.value))
                    if self.value == self.call:
                        self.stat = 'X'
                    for i in range(len(self.cq_lists)):
                        if self.cq_lists[i][0] == self.call:
                            self.cq_lists[i][9] = self.nowut
                            self.cq_list = self.cq_lists[i]
                            if self.stat == 'X' or self.cq_lists[i][2] == 'S':
                                self.cq_lists[i][2] = self.stat
                            if self.cq_lists[i][2] == ' ':
                                del self.cq_lists[i]
                                self.cq_list[3] = self.snr
                                self.cq_lists.insert(0,self.cq_list)
                            else:
                                self.cq_lists[i][3] = self.snr
                            self.c_cq_lists = 1
                            break

    def DCMessage3(self,ps):
        self.s_nowut = self.nowut
        self.client_id = ps.QString()
#        out3 = "Clear: %s" % (self.client_id)
        self.cq_lists = []
        self.c_cq_lists = 1
        self.frm.list_ctrl_data.DeleteAllItems()

    def DCMessage4(self,ps):
        self.client_id = ps.QString()
        self.timeb = ps.QInt32()
        self.time = ps.getDiffTime(self.timeb)
        self.reply_snr = ps.QInt32()
        self.delta_time = ps.QFloat()
        self.mode = ps.QString()
        self.message = ps.QString()
#        out3 = "Reply: %s %d %d %f %s %s" %\
#               (self.client_id\
#               ,self.time\
#               ,self.reply_snr\
#               ,self.delta_time\
#               ,self.mode\
#               ,self.message\
#               )

    def DCMessage5(self,ps):
        self.s_nowut = self.nowut

        self.qsos_raw, self.adif_header = adif_io.read_from_file(self.adif_path)
    
        self.client_id = ps.QString()
        self.date_time_off = ps.QDateTime()
        self.dx_call = ps.QString()
        self.dx_grid = ps.QString()
        self.dial_frequency = ps.QInt64()
        self.dial_frequency_s,self.band_n = ps.getDialFrequency(self.dial_frequency)
        self.mode = ps.QString()
        self.report_send = ps.QString()
        self.report_received = ps.QString()
        self.tx_power = ps.QString()
        self.comments = ps.QString()
        self.name = ps.QString()
        self.date_time_on = ps.QDateTime()
        self.details = ''
        for i in range(len(self.cq_lists)):
            if self.cq_lists[i][0] == self.dx_call:
                self.cq_lists[i][2] = 'X'
                self.cq_lists[i][9] = self.nowut
                self.details = self.cq_lists[i][8]
                self.c_cq_lists = 1
                break

#        out3 = "Logged: %s %s %s %s %s %s %s %s %s %s %s %s" %\
#               (client_id\
#               ,date_time_on\
#               ,dx_call\
#               ,dx_grid\
#               ,self.dial_frequency_s\
#               ,mode\
#               ,report_send\
#               ,report_received\
#               ,tx_power\
#               ,comments\
#               ,name\
#               ,date_time_off\
#               )
        self.cq_list = [self.call,self.grid,self.stat,0,self.freq_n,self.band_n,self.tx_mode,self.country,self.details,self.nowut]
        self.slackmsg = "%s %s %s %s %s %s" %\
               (\
                self.date_time_on\
               ,self.dx_call\
               ,self.dx_grid\
               ,self.dial_frequency_s\
               ,self.comments\
               ,self.details\
               )
        self.ft8slack.send_slack_message(self.slackmsg,self.channel_id_logged)
#        print("Logged")
#        print(f'Received message is [{pkt.hex()}]')

        self.HeadSetLabel()

    def DCMessage6(self,ps):
        self.s_nowut = self.nowut
        self.client_id = ps.QString()
#        out3 = "Close: %s" % (self.client_id)
        self.cq_lists = []
        self.c_cq_lists = 1
        self.frm.list_ctrl_data.DeleteAllItems()

    def DCMessage7(self,ps):
        self.client_id = ps.QString()
#        out3 = "Replay: %s" % (self.client_id)

    def DCMessage8(self,ps):
        self.client_id = ps.QString()
        self.auto_tx_only = ps.QInt8()
#        out3 = "HaltTx: %s %d" % (self.client_id,self.auto_tx_only)

    def DCMessage9(self,ps):
        self.s_nowut = self.nowut
        self.client_id = ps.QString()
        self.text = ps.QString()
        self.send = ps.QInt8()
#        out3 = "FreeText: %s %s %d" % (self.client_id,self.text,self.send)

    def DCMessage12(self,ps):
        self.s_nowut = self.nowut
        self.client_id = ps.QString()
        self.ADIF_text = ps.QString()
        self.qsos, self.header =  adif_io.read_from_string(self.ADIF_text)
        for i in range(len(self.cq_lists)):
            if self.cq_lists[i][0] == self.qsos[0]['CALL']:
                self.cq_lists[i][2] = 'X'
                self.cq_lists[i][9] = self.nowut
                self.c_cq_lists = 1
                break
#        out3 = "%s" % (self.ADIF_text)

    def HeadSetLabel(self):
#        self.frm.label_freq.Hide()
#        self.frm.label_band.Hide()
#        self.frm.label_mode.Hide()
#        self.frm.label_rx.Hide()
#        self.frm.label_tx.Hide()
        self.frm.label_freq.SetLabel(self.dial_frequency_s)
        self.frm.label_band.SetLabel(self.band_n)
        self.frm.label_mode.SetLabel(self.tx_mode)
        self.frm.label_rx.SetLabel("%4d" % (self.rx_df))
        self.frm.label_tx.SetLabel("%4d" % (self.tx_df))
#        self.frm.label_freq.Show()
#        self.frm.label_band.Show()
#        self.frm.label_mode.Show()
#        self.frm.label_rx.Show()
#        self.frm.label_tx.Show()

    def ServThread(self):
        global time
        self.qsos_raw, self.adif_header = adif_io.read_from_file(self.adif_path)
#        print(self.qsos_raw)
        self.sock = socket(AF_INET, SOCK_DGRAM)
        try:
            self.sock.bind((self.ip, int(self.num)))
        except:
            self.SetReceiving(False)
            self.sock.close()
            return

        self.cq_lists = []
        self.c_cq_lists = 0
        self.b_MessageType = -1
        self.MessageType = -1

        self.nowut = time.time()
        self.s_nowut = time.time()

        self.fds = set()
        self.fds.add(self.sock)

        self.HeadSetLabel()

#        self.ft8slack.send_slack_message('test',self.channel_id_ham)
        while(1):
            if not self.GetReceiving():
                break
                
            try:
                r, w, x = select.select(list(self.fds), [], [], 1)
                for s in r:
                    if s is self.sock:
                        #print('Received')
                        pkt, cliaddr = s.recvfrom(1024)

                        ps = PacketReader(pkt)
                        self.MessageType = ps.QInt32()

                        self.nowut = time.time()
                        self.s_nowdt = datetime.fromtimestamp(self.nowut-self.s_nowut, timezone.utc)
                        self.frm.SetTitle("ft8 "+self.s_nowdt.strftime('%H:%M:%S'))
                        if (self.nowut-self.s_nowut) > (1*60):
#                            wx.MessageBox('One hour has passed', 'メッセージ')
                            self.ft8slack.send_slack_message('One hour has passed',self.channel_id_ham)
                            self.s_nowut = time.time()

                        if self.MessageType == 0:
                            self.DCMessage0(ps)

                        elif self.MessageType == 1:
                            self.DCMessage1(ps)
                
                        elif self.MessageType == 2:
                            self.DCMessage2(ps)
                
                        elif self.MessageType == 3:
                            self.DCMessage3(ps)
                
                        elif self.MessageType == 4:
                            self.DCMessage4(ps)
                
                        elif self.MessageType == 5:
                            self.DCMessage5(ps)
                
                        elif self.MessageType == 6:
                            self.DCMessage6(ps)
                
                        elif self.MessageType == 7:
                            self.DCMessage7(ps)
                
                        elif self.MessageType == 8:
                            self.DCMessage8(ps)
                
                        elif self.MessageType == 9:
                            self.DCMessage9(ps)
                
                        elif self.MessageType == 12:
                            self.DCMessage12(ps)
                
                        else:
                            print('?????????????????')

#            except Exception as e:
#                print(e)
#                pass

            finally:
                time.sleep(0.5)

            if self.b_MessageType != self.MessageType:
                self.b_MessageType = self.MessageType
                if self.c_cq_lists == 1:
                    self.c_cq_lists = 0
#                    cq_list = [call,grid,stat,snr,freq_n,band_n,tx_mode,country,details]
#                    out4 = ''
#                    out4 = "%s %s %s %d %d" % (self.dial_frequency_s,self.band_n,self.tx_mode,self.rx_df,self.tx_df)
#                    out4 = out4 + '\n'
                    self.HeadSetLabel()
#                    self.frm.label_freq.SetLabel(self.dial_frequency_s)
#                    self.frm.label_band.SetLabel(self.band_n)
#                    self.frm.label_mode.SetLabel(self.tx_mode)
#                    self.frm.label_rx.SetLabel(self.rx_df)
#                    self.frm.label_tx.SetLabel(self.tx_df)

                    self.frm.list_ctrl_data.DeleteAllItems()
                    for i in range(len(self.cq_lists)):
                        cql = self.cq_lists[i]
#                        out4 = out4 + "%s %-10s %4s %3d %s" % (cql[2],cql[0],cql[1],cql[3],cql[8])
#                        out4 = out4 + '\n'
                        self.frm.list_ctrl_data.InsertItem(i, "%s" % (cql[2]))
                        self.frm.list_ctrl_data.SetItem(i, 1, "%-10s" % (cql[0]))
                        self.frm.list_ctrl_data.SetItem(i, 2, "%4s" % (cql[1]))
                        self.frm.list_ctrl_data.SetItem(i, 3, "%3d" % (cql[3]))
                        self.frm.list_ctrl_data.SetItem(i, 4, "%s" % (cql[8]))
                    for i in range(5):
                        self.frm.list_ctrl_data.SetColumnWidth(i,wx.LIST_AUTOSIZE)

        self.sock.close()
        return

if __name__ == "__main__":
    ft8dc = ft8dc(0)
