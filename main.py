import itertools
import re
import urllib.request

from bs4 import BeautifulSoup
import pandas as pd 
from igraph import Graph
import plotly.graph_objects as go


URLS = {
    "ФК": "http://roskazna.ru/opendata/",
    "ФНС": "http://nalog.ru/opendata/",
    "ФТС": "http://www.customs.ru/opendata/",
    "ФСРАР": "http://www.fsrar.ru/opendata/" 
}


def get_html(url):
    response = urllib.request.urlopen(url)
    return response.read()


def download_csv(html, link):
    """Скачиваем csv с данными и вытаскиваем из них  нужные данные"""

    domain = re.match(r"http(s)?://[a-z]+\.[a-z]+", link).group(0)  #  домен сайта, который парсим
    soup = BeautifulSoup(html, features="lxml")  #  объект BS для поиска по главной странице сайта
    a = soup.find('a', text=re.compile("Перечень подведомственных")) or soup.find('a', text=re.compile("Организации, находящиеся в ведении"))  # ссылка на страницу с подвед. орг.
    href = a['href'] if 'http' in a['href'] else domain + a['href']  #  приводим ссылку к виду http://домен...
    
    soup = BeautifulSoup(get_html(href), features="lxml")  #  объект BS для поиска по странице с подвед. орг.
    link = soup.find('a', href=re.compile(".csv"))['href']  #  ищем ссылку на скачивание csv файла с данными 
    link_to_download = link if 'http' in link else domain + link  #  приводим ссылку к виду http://домен...

    filename = './{}.csv'.format(domain[domain.index("//")+2:])  #  делаем понятное название файлов
    
    urllib.request.urlretrieve(link_to_download, filename)  #  скачиваем файл
    list_orgs = parse_csv(filename)  #  парсим файл и возвращаем список его подведомственных учреждений

    return list_orgs


def parse_csv(file_path):
    """
    Т.к. во всех файлах разные кодировки и разные разделители,
    делаем всемозможные пары кодировка+разделитель для чтения всех файлов
    """
    params = list(itertools.product(('cp1251', 'utf8', 'cp866'), (';', ',')))

    res = []  #  список подвед. учреж.

    # добавила try/except т к есть ломаные файлы, чтобы это не ломало всю программу
    for enc, sep in params:
        try:
            df = pd.read_csv(file_path, encoding=enc, sep=sep)  #  делаем датафрейм
            res = list(df[df.columns[1]].values)  #  вытаскиваем значения первого слолбика
        except:
            continue
        else:
            break

    return res


def dataset_to_graph(G, subtree, structure, parent=None, level=0):
    """Перенести иерархию учреждений, полученную после парсинга, в вид дерева путем обхода в глубину иерархии"""

    # бежим по вершинам дерева
    for node in subtree: 
        node_number = len(structure) # запоминаем номер вершины
        structure.append((node_number, node, level)) # добавляем узел в список-структуру дерева (номер узла, название узла, уровень вложенности)
        G.add_vertex(node_number) # добавляем вершину в граф

        # если у вершины есть предок, то добавляем ребро от предка к вершине
        if parent is not None:
            G.add_edge(parent, node_number)

        # если есть наследники, то делаем рекурсивно то же самое
        if isinstance(subtree, dict):
            dataset_to_graph(G, subtree[node], structure, node_number, level+1)


def draw_tree(dataset):
    # инициализируем граф
    G = Graph()

    # инициализируем структуру (список кортежей), в которой будет храниться информация о дереве в плоском виде
    structure = []

    # переводим дерево в плоскую иерархию, наполняем граф вершинами и ребрами
    dataset_to_graph(G, dataset, structure)

    # задаем размещение вершин на плоскости  (есть разные виды отображений, можно попробовать заменить rt на star)
    layout = G.layout("rt")

    # возвращает структуру вида ключ-значение, где ключ - номер вершины, а значение - координаты на плоскости (кортеж)
    position = {k: layout[k] for k in range(len(structure))}

    # максимальная y-координата
    M = max([v[1] for _, v in position.items()])

    # список ребер (кортеж)
    E = G.get_edgelist()

    # количество вершин
    L = len(position)

    # х-координаты всех вершин
    Xn = [position[k][0] for k in range(L)]

    # у-координаты всех вершин
    Yn = [2*M - position[k][1] for k in range(L)]

    Xe = [] # х-координаты всех ребер
    Ye = [] # у-координаты всех ребер

    for edge in E:
        Xe.extend([position[edge[0]][0], position[edge[1]][0], None])
        Ye.extend([2*M-position[edge[0]][1], 2*M-position[edge[1]][1], None])

    fig = go.Figure()

    # добавляем ребра на изображение
    fig.add_trace(
        go.Scatter(
            x=Xe,
            y=Ye,
            mode='lines',
            line=dict(color='rgb(210,210,210)', width=1),
            hoverinfo='none'
        )
    )

    # добавляем вершины на изображение
    fig.add_trace(
        go.Scatter(
            x=Xn,
            y=Yn,
            mode='markers',
            marker=dict(
                symbol='circle-dot',
                size=18,
                color='#6175c1',
                line=dict(
                    color='rgb(50,50,50)',
                    width=1
                )
            ),
            text=[item[1] for item in structure],
            hoverinfo='text',
            opacity=0.8
        )
    )

    # настройки отображения (оси, подписи и т.д.)
    axis = dict(
        showline=False, # hide axis line, grid, ticklabels and  title
        zeroline=False,
        showgrid=False,
        showticklabels=False,
    )

    # настройки изображения (подпись к рисунку, размеры шрифтов и т.д.)
    fig.update_layout(
        title='Подведомственные министерству финансов учреждения',
        font_size=12,
        showlegend=False,
        xaxis=axis,
        yaxis=axis,
        margin=dict(l=40, r=40, b=85, t=100),
        hovermode='closest',
        plot_bgcolor='rgb(248,248,248)'
    )

    # отобразить дерево
    fig.show()


def main():
    dataset = {"МинФин": {}}

    for title, url in URLS.items():
        list_orgs = download_csv(get_html(url), url)  #  список подвед. орг.
        dataset["МинФин"][title] = list_orgs  #  добавляем в словарь пару {название учреждения: [список подведом. орг.]}

    # код для отладки (чтобы читать файлы с диска, а не качать с сайтов)
    # titles = [
    #     "ФНС",
    #     "ФК",
    #     "ФТС",
    #     "ФСРАР"
    # ]

    # for title, path in zip(titles, ("nalog.ru.csv", "roskazna.ru.csv", "www.customs.csv", "www.fsrar.csv")):
    #     dataset["МинФин"][title] = parse_csv(path)

    draw_tree(dataset)  #  отрисовываем результат


if __name__ == "__main__":
    main()
