#!/usr/bin/env python3
import os
import sys
import json
import time
import requests
import subprocess
from os.path import expanduser
from . import coinslib, tuilib, binance_api

cwd = os.getcwd()
home = expanduser("~")

#TODO: change this to match python methods
def help_mm2(node_ip, user_pass):
    params = {'userpass': user_pass, 'method': 'help'}
    r = requests.post(node_ip, json=params)
    return r.text

def check_mm2_status(node_ip, user_pass):
    try: 
        help_mm2(node_ip, user_pass)
        return True
    except Exception as e:
        return False

def my_orders(node_ip, user_pass):
    params = {'userpass': user_pass, 'method': 'my_orders',}
    r = requests.post(node_ip, json=params)
    return r

def orderbook(node_ip, user_pass, base, rel):
    params = {'userpass': user_pass,
              'method': 'orderbook',
              'base': base, 'rel': rel,}
    r = requests.post(node_ip, json=params)
    return r

def check_active_coins(node_ip, user_pass, cointag_list, trading_cointag_list):
    active_cointags = []
    active_trading_cointags = []
    for cointag in cointag_list:
        try:
            # Dirty way to detect activation (rel is checked first by mm2)
            resp = orderbook(node_ip, user_pass, 'XXXX', cointag).json()
            if resp['error'] == 'Base coin is not found or inactive':
                active_cointags.append(cointag)
                if cointag in trading_cointag_list:
                    active_trading_cointags.append(cointag)
        except Exception as e:
            #print(e)
            pass
    return active_cointags, active_trading_cointags

def check_coins_status(node_ip, user_pass):
    if os.path.exists(cwd+"/coins") is False:
        msg = "'coins' file not found in "+cwd+"!"
        return msg, 'red'
    else:
        cointag_list = []
        for coin in coinslib.coins:
            cointag_list.append(coin)
        num_all_coins = len(cointag_list)
        trading_cointag_list = list(coinslib.trading_list.keys())
        num_trading_coins = len(trading_cointag_list)
        active_coins = check_active_coins(node_ip, user_pass, cointag_list, trading_cointag_list)
        #tuilib.wait_continue()
        num_active_coins = len(active_coins[0])
        num_active_trading_coins = len(active_coins[1])
        msg = str(num_active_coins)+"/"+str(num_all_coins)+" coins active, "\
            + str(num_active_trading_coins)+"/"+str(num_trading_coins)+" trading"
        if num_active_coins == 0:
            color = 'red'
            all_active = False
        elif num_active_coins < len(coinslib.coins):
            color = 'yellow'
            all_active = False
        else:
            color = 'green'
            all_active = True
        return msg, color, all_active, active_coins[0], active_coins[1]

def get_status(node_ip, user_pass):
    mm2_status = check_mm2_status(node_ip, user_pass)
    if mm2_status:
        mm2_msg = tuilib.colorize('{:^20}'.format("[MM2 active]"), 'green')
    else:
        mm2_msg = tuilib.colorize('{:^20}'.format("[MM2 disabled]"), 'red')
    coins_status = check_coins_status(node_ip, user_pass)
    coin_msg = tuilib.colorize('{:^35}'.format("["+coins_status[0]+"]"), coins_status[1])
    status_msg = mm2_msg+" "+coin_msg
    return status_msg, mm2_status, coins_status[2], coins_status[3], coins_status[4], 

def enable(node_ip, user_pass, cointag, tx_history=True):
    coin = coinslib.coins[cointag]
    params = {'userpass': user_pass,
              'method': 'enable',
              'coin': cointag,
              'mm2':1,  
              'tx_history':tx_history,}
    r = requests.post(node_ip, json=params)
    return r

def electrum(node_ip, user_pass, cointag, tx_history=True):
    coin = coinslib.coins[cointag]
    if 'contract' in coin:
        params = {'userpass': user_pass,
                  'method': 'enable',
                  'urls':coin['electrum'],
                  'coin': cointag,
                  'swap_contract_address': coin['contract'],
                  'mm2':1,
                  'tx_history':tx_history,}
    else:
        params = {'userpass': user_pass,
                  'method': 'electrum',
                  'servers':coin['electrum'],
                  'coin': cointag,
                  'mm2':1,
                  'tx_history':tx_history,}
    r = requests.post(node_ip, json=params)
    return r
    

def my_balance(node_ip, user_pass, cointag):
    params = {'userpass': user_pass,
              'method': 'my_balance',
              'coin': cointag,}
    r = requests.post(node_ip, json=params)
    return r

def build_coins_data(coins):
    coins_data = {}
    cointags = []
    gecko_ids = []
    print('Getting prices from Binance...')
    for coin in coins:
      coins_data[coin] = {}
      cointags.append(coin)
      if coin == 'BCH':
        ticker_pair = 'BCHABCBTC'
      elif coin == 'BTC':
        ticker_pair = 'BTCBTC'
        coins_data[coin]['BTC_price'] = 1
      else:
        ticker_pair = coin+'BTC'
      # Get BTC price from Binance
      resp = binance_api.get_price(ticker_pair)
      if 'price' in resp:
        coins_data[coin]['BTC_price'] = float(resp['price'])
      else:
        coins_data[coin]['BTC_price'] = 0
    # Get Coingecko API ids
    print('Getting prices from CoinGecko...')
    gecko_coins_list = requests.get(url='https://api.coingecko.com/api/v3/coins/list').json()
    for gecko_coin in gecko_coins_list:
      if gecko_coin['symbol'].upper() in cointags:
        # override to avoid batcoin
        if gecko_coin['symbol'].upper() == 'BAT':
          coins_data[gecko_coin['symbol'].upper()]['gecko_id'] = 'basic-attention-token'
          gecko_ids.append('basic-attention-token')
        else:
          coins_data[gecko_coin['symbol'].upper()]['gecko_id'] = gecko_coin['id']
          gecko_ids.append(gecko_coin['id'])

    # Get fiat price on Coingecko
    gecko_prices = gecko_fiat_prices(",".join(gecko_ids), 'usd,aud,btc').json()
    for coin_id in gecko_prices:
      for coin in coins_data:
        if 'gecko_id' in coins_data[coin]:
          if coins_data[coin]['gecko_id'] == coin_id:
            coins_data[coin]['AUD_price'] = gecko_prices[coin_id]['aud']
            coins_data[coin]['USD_price'] = gecko_prices[coin_id]['usd']
            if coins_data[coin]['BTC_price'] == 0:
              coins_data[coin]['BTC_price'] = gecko_prices[coin_id]['btc']
        else:
          coins_data[coin]['AUD_price'] = 0
          coins_data[coin]['USD_price'] = 0
    return coins_data

def gecko_fiat_prices(gecko_ids, fiat):
    url = 'https://api.coingecko.com/api/v3/simple/price'
    params = dict(ids=str(gecko_ids),vs_currencies=fiat)
    r = requests.get(url=url, params=params)
    return r