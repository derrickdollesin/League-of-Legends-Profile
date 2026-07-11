import os
import time
import requests
import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("RIOT_API_KEY")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Charset": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://developer.riotgames.com"
}

def get_puuid(game_name, tag_line):
    '''
    Get Riot's Player Universally Unique Identify (PUUID)

    Args:
        - game_name: (string)
        - tag_line: (string)

    Returns:
        - payload response with keys: [puuid, gamename, tag] (dictionary)
    '''
    url = f'https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}?api_key={API_KEY}'

    try:
        response = requests.get(url, headers=HEADERS)

        response.raise_for_status()
        
        json_response = response.json()
    except Exception as e:
        print(f"Error fetching URL: {e.reason}")

    return json_response['puuid']

def get_match_ids(puuid, start_time=1623801600, end_time=int(time.time()), game_type='ranked'):
    ''' 
    Get a list of recent matches. Top ID will be the last played game. 

    Args:
        - puuid: player id (string)
        - start_time: Epoch time of start timeframe (long)
        - end_time: Epoch time of end timeframe (long)
        - game_type: gamemode played (string)

    Returns:
        - List of games played (list)
    '''
    url = f'https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?startTime={start_time}&endTime={end_time}&type={game_type}&start=0&count=20&api_key={API_KEY}'

    try:
        response = requests.get(url, headers=HEADERS)

        response.raise_for_status()
        
        json_response = response.json()
    except Exception as e:
        print(f"Error fetching URL: {e.reason}")

    return json_response
        

def get_match_data(match_id):
    ''' 
    Returns match data for specific played game

    Args:
        - match_id: unique identifier for game played (string)

    Returns:
        - Dictionary of match data:
            - match_data
            - timeline_data
    '''
    match_url = f'https://americas.api.riotgames.com/lol/match/v5/matches/{match_id}?api_key={API_KEY}'
    timeline_url = f'https://americas.api.riotgames.com/lol/match/v5/matches/{match_id}/timeline?api_key={API_KEY}'

    try:
        match_response = requests.get(match_url, headers=HEADERS)
        timeline_response = requests.get(timeline_url, headers=HEADERS)

        match_response.raise_for_status()
        timeline_response.raise_for_status()

        match_data = match_response.json()
        timeline_data = timeline_response.json()

    except Exception as e:
        print(f"Error fetching URL: {e.reason}")

    ### Timeline Data

    participantids = []
    playerpuuids = []

    for player in timeline_data['info']['participants']:
        participantId = player['participantId']
        playerPuuid = player['puuid']

        if len(playerPuuid) != 78:
            print(f'Error Getting Puuid for Participant {participantId}')
            playerPuuid = np.nan

        participantids.append(participantId)
        playerpuuids.append(playerPuuid)

    if len(participantids) != len(playerpuuids):
        print('Error creating dataframe')
    else:
        data = {
            'player_number': participantids,
            'puuid': playerpuuids
        }

        player_map = pd.DataFrame(data)

    champ_stats_frames = []
    damage_stats_frames = []
    position_frames = []
    misc_frames = []
    for i in range(len(timeline_data['info']['frames'])):
        for player in player_map['player_number'].to_list():
            frame = timeline_data['info']['frames'][i]['participantFrames'][f'{player}']

            champ_stats = frame['championStats']
            damage_stats = frame['damageStats']
            position = frame['position']

            keys = [
                key for key in list(
                    frame.keys()
                ) if key not in ['championStats', 'damageStats', 'position']
            ]
            misc_stats = {key: frame[key] for key in keys}

            champ_stats['currentFrame'] = i + 1
            champ_stats['participantId'] = player
            damage_stats['currentFrame'] = i + 1
            damage_stats['participantId'] = player
            position['currentFrame'] = i + 1
            position['participantId'] = player

            misc_stats['currentFrame'] = i + 1

            champ_stats_frames.append(champ_stats)
            damage_stats_frames.append(damage_stats)
            position_frames.append(position)
            misc_frames.append(misc_stats)

    champ_stats = pd.DataFrame(champ_stats_frames)
    damage_stats = pd.DataFrame(damage_stats_frames)
    positions = pd.DataFrame(position_frames)
    misc_stats = pd.DataFrame(misc_frames)

    timeline_output = {
        'player_map': player_map,
        'champ_stats': champ_stats,
        'damage_stats': damage_stats,
        'positions': positions,
        'misc_stats': misc_stats
    }

    ### Match Data

    bans = []
    for team in match_data['info']['teams']:
        ban = team['bans']
        for i in ban:
            bans.append(i)

    bans = (
        pd
        .DataFrame(bans)
        .rename(columns={
            'championId':'bannedChampionId', 
            'pickTurn':'participantId'
        })
    )

    data = []
    for i in range(len(match_data['info']['participants'])):
        keys = [
            key for key in list(
                match_data['info']['participants'][i].keys()
            ) if key not in ['PlayerBehavior', 'challenges', 'missions', 'perks']
        ]

        data.append({key: match_data['info']['participants'][i][key] for key in keys})

    data = pd.DataFrame(data)
    data = data.merge(bans, on='participantId', how='left')

    general_match_data = data[[col for col in data if 'PlayerScore' not in col]]

    match_data_output = {
        'general_match_data': general_match_data
    }

    return [timeline_output, match_data_output]


def get_player_rank(puuid):
    ''' 
    Returns a players rank for solo/duo queue and flex

    Args:
        - puuid: unique player id (string)

    Returns:
        - (dictionary)
    '''
    url = f'https://na1.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}?api_key={API_KEY}'

    try:
        response = requests.get(url, headers=HEADERS)

        response.raise_for_status()
        
        json_response = response.json()
    except Exception as e:
        print(f"Error fetching URL: {e.reason}")

    return json_response


def get_player_champion_mastery(puuid, champion_id):
    ''' 
    Returns a players champion mastery data.

    Args:
        - puuid: unique player id (string)
        - champion_id: riot champion id (int)

    Returns:
        - (dictionary)
    '''
    url = f'https://na1.api.riotgames.com/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}/by-champion/{champion_id}?api_key={API_KEY}'
    
    try:
        response = requests.get(url, headers=HEADERS)

        response.raise_for_status()
        
        json_response = response.json()
    except Exception as e:
        print(f"Error fetching URL: {e.reason}")

    return json_response