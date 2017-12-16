from elasticsearch import Elasticsearch
from tqdm import tqdm
import requests
import lxml.html
import lxml.etree
import sqlite3
import time
import os.path

es = Elasticsearch()
last_update = -1
bot_url = ""

def load_news(path, db_name, start_year, fin_year):
    
    f = open(path + db_name + '.db', 'a')
    f.close()
    conn = sqlite3.connect(path + db_name + '.db')
    cursor = conn.cursor()
    cursor.execute('create table if not exists news (id integer not null, category integer, title text, article text, link text, primary key (id), foreign key (category) references categories(id))')
    conn.commit()
    f = open(path + db_name + '.txt', 'w', encoding='utf8')
    for year in tqdm(range(start_year, fin_year + 1)):
        for month in tqdm(range(1, 13), leave = False):
            if month == 2:
                i = 30
            else:
                i = 32
            for day in tqdm(range(1, i), leave = False):
                if month < 10:
                    m = '0'
                else:
                    m = ''
                if day < 10:
                    d = '0'
                else:
                    d = ''
                num = 0
                while True:
                    num = num + 1
                    article = ''
                    if num < 10:
                        article = article + '0'
                    if num < 100:
                        article = article + '0'
                    article = article + str(num)
                    s_year = str(year)
                    s_mon = m + str(month)
                    s_day = d + str(day)
                    db_id = s_year + s_mon + s_day + article
                    cursor.execute('select id from news where id = ' + db_id)
                    r = cursor.fetchall()
                    if len(r) == 0:
                        url = 'http://www.fontanka.ru/' + s_year + '/' + s_mon + '/' + s_day + '/' + article
                        response = requests.get(url)
                        if(response.status_code != 200):
                            break
                        tree = lxml.html.fromstring(response.text)
                        t = tree.xpath('//span[contains(@class, "light")]/text()')                #категория
                        if len(t) > 0:
                            category = ((t[0]).replace('"', '´´')).replace("'", "´")
                        else:
                            category = ""
                        t = tree.xpath('//h1[contains(@class, "article_title")]/text()')          #заголовок  
                        if len(t) > 0:
                            title = ((t[0]).replace('"', '´´')).replace("'", "´")
                        else:
                            title = ""
                        t = tree.xpath('//div[contains(@class, "article_fulltext")]/p/text()')    #текст
                        if len(t) > 0:
                            article = ((t[0]).replace('"', '´´')).replace("'", "´")
                        else:
                            article = ""
                        f.write(db_id + "\n" + category + "\n" + title + '\n' + article + '\n\n')
                        cursor.execute('insert into news values (' + db_id + ', "' + category + '", "' + title + '", "' + article + '", "' + url + '")')
                        conn.commit()
    f.close()
    conn.close()
    """   
    except:
        return False
    else:
        return True
    """

def load_news_retr(path, db_name, start_year, fin_year, c):
    i = 0
    while i < c and not (load_news(path, db_name, start_year, fin_year)):
        i += 1
        time.sleep(5)
        
#Telegram bot
def req(method, params):
    return requests.post(bot_url + method, params)

def get_updates(timeout = 30):
    global last_update
    params = {'timeout': timeout, 'offset': last_update + 1}
    response = (req('getUpdates', params)).json()
    if response['ok']:
        if len(response['result']) > 0:
            last_update = response['result'][-1]['update_id']
        return response
    return False

def send_message(chat_id, text):
    params = {'chat_id': chat_id, 'text': text}
    return (req('sendMessage', params)).json()

#Поиск
def index(path, db_name):
    es.indices.create(index='news')
    f = open(path + db_name + '.db', 'a')
    f.close()
    conn = sqlite3.connect(path + db_name + '.db')
    cursor = conn.cursor()
    cursor.execute('select category, title, article, link from news')
    result = cursor.fetchall()
    for item in tqdm(result):
        es.index(index = 'news', doc_type = 'news', body={'category': item[0], 'title': item[1], 'article': item[2], 'link': item[3]})
    conn.close()
    
def search(text):
    t = es.search(index='news', doc_type='news', q=text)
    r = []
    for i in range(len(t['hits']['hits'])):
        tm = t['hits']['hits'][i]['_source']
        r.append((tm['title']).replace('\n', '').replace('\t', '') + '\n' + (tm['article']).replace('\n', '').replace('\t', '') +  '\n\n' + tm['link'])
    return r

def main():
    path = 'D:\\news\\'
    db_name = 'news_es'
    master_id = 0
    start_year = 2015
    fin_year = 2017
    
    while True:
        r = get_updates()
        if(r):
            for i in r['result']:
                text = i['message']['text']
                chat_id = i['message']['chat']['id']
                u_id = i['message']['from']['id']
                if u_id != chat_id:
                    continue
                if u_id == master_id:
                    t_low = text.lower()
                    if (t_low == '/load_news'):
                        send_message(chat_id, 'Загрузка новостей...')
                        if load_news(path, db_name, start_year, fin_year):
                            send_message(chat_id, 'Успешно')
                        else:
                            send_message(chat_id, 'Ошибка')
                        continue
                    if (t_low == '/index'):
                        send_message(chat_id, 'Индексация...')
                        index(path, db_name)
                        send_message(chat_id, 'Выполнено.')
                        continue
                    if (t_low == '/stop_bot'):
                        send_message(chat_id, 'Остановка бота.')
                        get_updates(1)
                        return
                if text == '/start':
                    send_message(chat_id, 'Отправьте боту поисковой запрос для получения новости')
                    continue
                try:
                    s = search(text)
                    for item in s:
                        send_message(chat_id, item)
                except:
                    send_message(chat_id, 'Ошибка')
    return

if __name__ == '__main__':  
    try:
        main()
    except KeyboardInterrupt:
        exit()
    
    

