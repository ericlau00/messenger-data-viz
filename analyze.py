import os
import time
import json
from string import punctuation
from datetime import datetime, timedelta

import nltk
import emoji
import regex

fp = os.path.dirname(os.path.abspath(__file__))
inbox = f"{fp}/messages/inbox"


def strtodate(string):
    return datetime.strptime(string, '%Y-%m-%d')


def find_percentage_by_day(data, totals):
    for c_id in data.keys():
        convo = data[c_id]
        convo['percent_per_day'] = dict()
        for date in convo['msgs_per_day'].keys():
            percent = convo['msgs_per_day'][date] / totals[date] * 100
            convo['percent_per_day'][date] = percent


def find_per_info(data):
    increment = 'daily'
    stack_msgs_by_day = dict()
    total_by_day = dict()

    names = {key: data[key]['name'] for key in data.keys()}

    convo_ids = data.keys()
    for c_id in convo_ids:

        msgs = data[c_id]['msgs_per_day']
        for date in msgs.keys():
            if not date in stack_msgs_by_day:
                stack_msgs_by_day[date] = dict()

                for id in convo_ids:
                    stack_msgs_by_day[date][id] = 0

            stack_msgs_by_day[date][c_id] = msgs[date]

            if not date in total_by_day:
                total_by_day[date] = msgs[date]
            else:
                total_by_day[date] += msgs[date]

    keys = list(sorted(stack_msgs_by_day.keys()))

    i = 0
    length = len(keys) - 1
    while i < length:
        currD = strtodate(keys[i])
        nextD = strtodate(keys[i+1])
        diff = nextD - currD
        distance = diff.days
        for j in range(distance - 1):
            tmp = currD + timedelta(j + 1)
            string = tmp.isoformat()[:10]
            stack_msgs_by_day[string] = dict()
            for id in convo_ids:
                stack_msgs_by_day[string][id] = 0
            keys.insert(i+j+1, string)
        length = len(keys) - 1
        i += distance

    dates = [strtodate(date) for date in keys]
    if len(dates) > 365 * 2:
        increment = 'weekly'
        tmp_msg_dict = dict()
        one_day = timedelta(days=1)
        while dates[0].weekday() != 6:
            day_before = dates[0] - one_day
            string = day_before.isoformat()[:10]
            stack_msgs_by_day[string] = dict()
            for id in convo_ids:
                stack_msgs_by_day[string][id] = 0
            dates.insert(0, day_before)
        curr_week = dates[0]
        for i in range(len(dates)):
            if dates[i].weekday() == 6:
                curr_week = dates[i]
            else:
                week_str = curr_week.isoformat()[:10]
                curr_str = dates[i].isoformat()[:10]

                for name in stack_msgs_by_day[curr_str].keys():
                    stack_msgs_by_day[week_str][name] += stack_msgs_by_day[curr_str][name]

                stack_msgs_by_day.pop(curr_str)

    msg_list = list()
    for date in sorted(stack_msgs_by_day.keys()):

        count_val = stack_msgs_by_day[date]
        count_val = {names[key]: count_val[key] for key in count_val}
        count_val['date'] = date

        msg_list.append(count_val)

    return increment, msg_list, total_by_day


def get_msgs_by_time(messages):
    msgDateMap = dict()

    msgMinuteList = list()
    for i in range(24):
        msgMinuteList.append(list())
        for j in range(60):
            msgMinuteList[i].append(0)

    for msg in messages:
        t = int(msg['timestamp_ms']) / 1000
        date = datetime.fromtimestamp(t)
        iso = date.isoformat()[:10]

        if not iso in msgDateMap:
            msgDateMap[iso] = 1
        else:
            msgDateMap[iso] += 1

        msgMinuteList[date.hour][date.minute] += 1

    msgs_by_minute = list()
    for data in msgMinuteList:
        msgs_by_minute.extend(data)

    return msgDateMap, msgs_by_minute


def find_current_percentage(data, total):
    for d in data:
        d['percent'] = d['number'] / total * 100

    return sorted(data, key=lambda x: x['number'], reverse=True)


def get_conversation(convo):
    tmp = {'number': 0, 'messages': list()}
    msg_files = [f.name for f in os.scandir(f"{inbox}/{convo}") if f.is_file()]
    for msg_file in msg_files:
        fi = open(f"{inbox}/{convo}/{msg_file}")
        f = json.load(fi)
        fi.close()

        if not 'name' in tmp:
            title = f['title'].encode('latin-1').decode('utf-8')
            tmp['name'] = title

        msgs = f['messages']
        tmp['number'] += len(msgs)
        tmp['messages'].extend(msgs)

    return tmp


def get_msg_split(messages):
    split_dict = dict()
    for msg in messages:
        name = msg['sender_name']
        if name not in split_dict:
            split_dict[name] = list()
        split_dict[name].append(msg)

    split_list = list()
    for name in split_dict.keys():
        split_list.append({
            'name': name.encode('latin-1').decode('utf-8'),
            'number': len(split_dict[name]),
            'percent': len(split_dict[name]) / len(messages) * 100
        })
    return split_list


def get_emoji_analysis(content):
    text = str()
    for c in content:
        text += c + ' '
    emoji_dict = dict()
    emoji_list = list()
    count = 0
    for word in regex.findall(r'\X', text):
        if any(char in emoji.UNICODE_EMOJI for char in word):
            count += 1
            if not word in emoji_dict:
                emoji_dict[word] = 1
            else:
                emoji_dict[word] += 1
            emoji_list.append(word)
    return emoji_dict, emoji_list, count


def generate_count_list(tokens, limit):
    vocab = nltk.FreqDist(tokens)
    common = vocab.most_common(limit)
    return [{'text': word[0], 'count': word[1]} for word in common if word[1] > 1]


def get_text_length(content):
    length = 0
    for text in content:
        length += len(text)
    return length / len(content) if len(content) > 0 else 0


def get_lang_processing(messages):
    content = [d['content'].encode('latin-1').decode('utf-8')
               for d in messages if 'content' in d]

    text_length = get_text_length(content)

    emoji_dict, emoji_list, emoji_count = get_emoji_analysis(content)

    standalone_vocab = nltk.FreqDist(content)
    standalone_count = generate_count_list(standalone_vocab, 100)

    standalone_total = 0
    for text in standalone_count:
        standalone_total += text['count']

    return {
        'emoji': {
            'breakdown': emoji_dict,
            'list': emoji_list,
            'count': emoji_count
        },
        'text_count': {
            'count': standalone_count,
            'total': standalone_total
        },
        'text_length': text_length
    }


def findStreak(dates):
    maxdiff = timedelta(days=1)
    streak = longest_streak = 1
    start = end = longest_start = longest_end = dates[0]
    for i in range(len(dates) - 1):
        diff = dates[i+1] - dates[i]
        if diff <= maxdiff:
            streak += 1
            end = dates[i+1]
            if streak >= longest_streak:
                longest_streak = streak
                longest_start = start
                longest_end = end
        else:
            streak = 1
            start = dates[i+1]
    return {
        'length': longest_streak,
        'start': longest_start.isoformat()[:10],
        'end': longest_end.isoformat()[:10]
    }


def get_max_day(msgs_per_day):
    date = max(msgs_per_day, key=msgs_per_day.get)
    value = msgs_per_day[date]
    return {'date': date, 'value': value}


def aggregate_data():

    convo_dirs = [f.name for f in os.scandir(inbox)]

    current_percent = list()
    conversations = dict()
    total = 0

    for convo in convo_dirs:
        convo_info = get_conversation(convo)
        subtotal = convo_info['number']
        name = convo_info['name']
        msgs = convo_info['messages']

        print('Analyzing messages from', name)

        total += subtotal
        current_percent.append({'number': subtotal, 'name': name})

        msgs_by_day, msgs_by_minute = get_msgs_by_time(msgs)

        msg_split = get_msg_split(msgs)

        dates = list(msgs_by_day.keys())
        dates = [strtodate(date) for date in dates]
        dates = sorted(dates)

        streak_info = findStreak(dates)

        lang_processing = get_lang_processing(msgs)

        max_msgs_in_day = get_max_day(msgs_by_day)

        conversations[convo] = {
            'name': name,
            'msgs_per_day': msgs_by_day,
            'msgs_per_minute': msgs_by_minute,
            'split': msg_split,
            'emoji': lang_processing['emoji'],
            'text_count': lang_processing['text_count'],
            'text_length': lang_processing['text_length'],
            'streak': streak_info,
            'max': max_msgs_in_day,
            'total': subtotal
        }

    return current_percent, conversations, total


def create_data_dump(data):

    current_percent, conversations, total = data

    increment, msgs_per, total_per_day = find_per_info(conversations)
    find_percentage_by_day(conversations, total_per_day)
    current_percent = find_current_percentage(current_percent, total)

    content = {
        'collective': {
            'total': total,
            'current_percent': current_percent,
            'msgs_per': {
                'data': msgs_per,
                'increment': increment
            },
        },
        'individual': {
            'info': conversations
        }
    }

    return content


if __name__ == "__main__":
    start = time.time()

    writefile = f"{fp}/data.json"

    data = aggregate_data()
    content = create_data_dump(data)

    with open(writefile, 'w', encoding='utf-8') as file:
        json.dump(content, file, ensure_ascii=False)

    print(time.time() - start, "seconds")
