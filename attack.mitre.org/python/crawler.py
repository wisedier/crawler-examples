import collections
import pathlib
from concurrent import futures

import bs4
import requests

DATA_DIR = pathlib.Path('.') / 'data'
Technique = collections.namedtuple('Technique', 'id, name')


def fetch_data(session: requests.Session, group_id: str, url: str):
    res = session.get(url)
    if res.status_code != 200:
        return None
    return group_id, res.text


def crawl_enterprise_matrix(session: requests.Session):
    url = 'https://attack.mitre.org/beta/matrices/enterprise/'
    res = session.get(url)
    soup = bs4.BeautifulSoup(res.text, 'lxml')
    matrix = collections.defaultdict(list)

    tactics = [*map(lambda el: el.text.strip(), soup.select('.matrix.side .tactic.name'))]
    tables = soup.select('.techniques-table')
    for i, table in enumerate(tables):
        tactic = tactics[i]
        tech_anchors = table.select('.technique-cell a')
        for anchor in tech_anchors:
            container = anchor.parent.parent
            if container.has_attr('class') and container.attrs['class'][0] == 'subtechnique':
                continue

            if (dummy := anchor.find('sub')) is not None:
                dummy.extract()

            tech_id = anchor.attrs['href'].strip().split('/')[-1]
            tech_name = anchor.text.strip()
            matrix[tactic].append(Technique(tech_id, tech_name))
    return matrix

def crawl_groups(session: requests.Session, pool: futures.ThreadPoolExecutor):
    tasks = []
    url = 'https://attack.mitre.org/beta/groups/'
    res = session.get(url)
    soup = bs4.BeautifulSoup(res.text, 'lxml')
    group_anchors = soup.select('.sidenav-head > a')

    for anchor in group_anchors:
        resources = anchor.attrs['href'].strip('/').split('/')
        if len(resources) == 1:
            continue

        group_id = resources[-1]
        group_url = f'{url}{group_id}/{group_id}-enterprise-layer.json'
        tasks.append(pool.submit(fetch_data, session, group_id, group_url))
    
    for task in futures.as_completed(tasks):
        if (result := task.result()) is None:
            continue

        group_id, data = result
        data_path = DATA_DIR / f'{group_id}.json'
        with data_path.open('w') as f:
            f.write(data)


def crawl():
    session = requests.Session()
    pool = futures.ThreadPoolExecutor()
    crawl_enterprise_matrix(session)
    crawl_groups(session, pool)
    pool.shutdown()
