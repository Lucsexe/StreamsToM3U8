#! /usr/bin/python3
import os
from datetime import datetime, timedelta
from urllib.parse import urlparse

import pytz
import requests
from lxml import etree
from bs4 import BeautifulSoup
import subprocess

tz = pytz.timezone('Europe/London')
channels = []


def generate_times(curr_dt: datetime):
    """
Generate 3-hourly blocks of times based on a current date
    :param curr_dt: The current time the script is executed
    :return: A tuple that contains a list of start dates and a list of end dates
    """
    # Floor the last hour (e.g. 13:54:00 -> 13:00:00) and add timezone information
    last_hour = curr_dt.replace(microsecond=0, second=0, minute=0)
    last_hour = tz.localize(last_hour)
    start_dates = [last_hour]

    # Generate start times that are spaced out by three hours
    for x in range(7):
        last_hour += timedelta(hours=3)
        start_dates.append(last_hour)

    # Copy everything except the first start date to a new list, then add a final end date three hours after the last
    # start date
    end_dates = start_dates[1:]
    end_dates.append(start_dates[-1] + timedelta(hours=3))

    return start_dates, end_dates


def build_xml_tv(streams: list) -> bytes:
    """
Build an XMLTV file based on provided stream information
    :param streams: List of tuples containing channel/stream name, ID and category
    :return: XML as bytes
    """
    data = etree.Element("tv")
    data.set("generator-info-name", "youtube-live-epg")
    data.set("generator-info-url", "https://github.com/dp247/YouTubeToM3U8")

    for stream in streams:
        channel = etree.SubElement(data, "channel")
        channel.set("id", stream[1])
        name = etree.SubElement(channel, "display-name")
        name.set("lang", "en")
        name.text = stream[0]

        dt_format = '%Y%m%d%H%M%S %z'
        start_dates, end_dates = generate_times(datetime.now())

        for idx, val in enumerate(start_dates):
            programme = etree.SubElement(data, 'programme')
            programme.set("channel", stream[1])
            programme.set("start", val.strftime(dt_format))
            programme.set("stop", end_dates[idx].strftime(dt_format))

            title = etree.SubElement(programme, "title")
            title.set('lang', 'en')
            title.text = stream[3] if stream[3] != '' else f'LIVE: {stream[0]}'
            description = etree.SubElement(programme, "desc")
            description.set('lang', 'en')
            description.text = stream[4] if stream[4] != '' else 'No description provided'
            icon = etree.SubElement(programme, "icon")
            icon.set('src', stream[5])

    return etree.tostring(data, pretty_print=True, encoding='utf-8')


def grab_youtube(url: str):
    """
    Grabs the live-streaming M3U8 file from YouTube using yt-dlp
    :param url: The YouTube URL of the livestream
    """
    if '&' in url:
        url = url.split('&')[0]

    try:
        # Usar yt-dlp para obtener el enlace M3U8
        m3u8_url = subprocess.check_output(["yt-dlp", "-f", "best", "-g", url]).decode().strip()
        if not m3u8_url or "m3u8" not in m3u8_url:
            print("https://github.com/ExperiencersInternational/tvsetup/raw/main/staticch/no_stream_2.mp4")
            return

        # Obtener metadatos para el EPG (opcional, pero lo mantenemos para compatibilidad)
        requests.packages.urllib3.disable_warnings()
        stream_info = requests.get(url, timeout=15)
        soup = BeautifulSoup(stream_info.text, features="html.parser")
        stream_title = soup.find("meta", property="og:title")["content"]
        stream_desc = soup.find("meta", property="og:description")["content"]
        stream_image_url = soup.find("meta", property="og:image")["content"]
        channels.append((channel_name, channel_id, category, stream_title, stream_desc, stream_image_url))

        print(m3u8_url)
    except Exception as e:
        print(f"Error obteniendo M3U8 para {url}: {e}")
        print("https://github.com/ExperiencersInternational/tvsetup/raw/main/staticch/no_stream_2.mp4")
        return


channel_name = ''
channel_id = ''
category = ''

# Open text file and parse stream information and URL
with open('./streams.txt', encoding='utf-8') as f:
    print("#EXTM3U")
    for line in f:
        line = line.strip()
        if not line or line.startswith('##'):
            continue
        if not (line.startswith('https:') or line.startswith('http:')):
            line = line.split('||')
            channel_name = line[0].strip()
            channel_id = line[1].strip()
            category = line[2].strip().title()
            print(
                f'\n#EXTINF:-1 tvg-id="{channel_id}" tvg-name="{channel_name}" group-title="{category}", {channel_name}')
        else:
            if urlparse(line).netloc == 'www.youtube.com':
                grab_youtube(line)
            elif urlparse(line).netloc == 'www.dailymotion.com':
                grab_dailymotion(line)
            elif urlparse(line).netloc == 'www.twitch.tv':
                grab_twitch(line)

# Time to build an XMLTV file based on stream data
channel_xml = build_xml_tv(channels)
with open('epg.xml', 'wb') as f:
    f.write(channel_xml)
    f.close()

# Remove temp files from project dir
if 'temp.txt' in os.listdir():
    os.system('rm temp.txt')
    os.system('rm watch*')
