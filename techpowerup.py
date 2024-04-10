from bs4 import BeautifulSoup
from bs4.element import Tag

from class_database import db, Components
from custom_request import request_get_v2
from component_classes.class_gpu import PCIe
from component_classes.class_ram import RAM


BASE_URL = 'https://www.techpowerup.com'
LINKS = {Components.CPU.value: BASE_URL + "/cpu-specs/", Components.GPU.value: BASE_URL + "/gpu-specs/"}


def parse_labels(website_link: str) -> list:
    def filter_labels():
        nonlocal labels
        for label in labels:
            if 'title' in label.attrs:
                if label['title'] == 'Close':
                    labels.pop(labels.index(label))

    labels = []
    main_page = BeautifulSoup(request_get_v2(website_link).content, features='html.parser')
    for fieldset in main_page.find_all('fieldset'):
        if 'filters' in fieldset['class']:
            labels = fieldset.find_all_next('label')
            filter_labels()
            return labels
    return labels


def get_labels_with_values(component: Components) -> dict[Components, list]:
    if component.value not in LINKS.keys():
        return {'error': f'updating {component} is not possible'}

    def remove_parenthesis(string: str) -> str:
        # TODO: figure our whether we need this at all
        start = string.find('(')
        end = string.find(')')
        if start != -1 and end != -1 and end > start:
            return string[0:start].strip()
        return string

    result = {}
    for label in parse_labels(LINKS[component.value]):
        siblings = []
        for sibling in label.next_siblings:
            if type(sibling) == Tag:
                siblings.append(sibling.contents)
        result.update({label['for']: siblings})
    for property_name, options_list in result.items():
        temp = []
        for option in options_list[0]:
            if type(option) == Tag:
                if option['value'] != "":
                    temp.append(option['value'])
        result.update({property_name: temp})
    return result


# noinspection PyTypeChecker
def get_component_list(component: Components, params: dict = None, sort_by: str = 'name') -> dict[Components, list]:
    if component.value not in LINKS.keys():
        return {'error': f'updating {component} is not possible'}
    if sort_by not in ['name', 'released', 'generation']:
        return {'error': f"You can't sort by {sort_by}"}

    if params is not None:
        allowed_filters = db.get_filters(component)[component]

        for filter_name, value in params.items():
            if filter_name not in allowed_filters.keys():
                return {'error': f"There is no such filter as {filter_name}"}
            elif value not in allowed_filters[filter_name]:
                return {'error': f"There is no such option as {value} in filter {filter_name}"}
        # up to here, the values are definitely correct

        query = "?"
        for _filter, value in params.items():
            query += f"{_filter}={value}&"
        query += f'sort={sort_by}'
    else:
        query = ""
    response = request_get_v2(f"{LINKS[component.value]}{query}")
    page = BeautifulSoup(response.text, features='html.parser')

    table = page.find('div', id="list").find('table')
    headers_row = table.find('thead', {"class": ['colheader']}).find('tr')
    headers = []
    for header in headers_row.contents:
        if type(header) == Tag:
            if header.name == 'th':
                headers.append(header.text)

    result = []
    for row in table.find_all('tr')[2:]:
        count = 0
        tpu_component = {}
        link = row.find('a').attrs['href']
        tpu_component.update({"Link": BASE_URL + link})
        for element in row.contents:
            if type(element) != Tag:
                continue
            tpu_component.update({headers[count]: element.text.replace("\n", "").strip()})
            count += 1
        result.append(tpu_component)

    return {component: result}


def get_cpu_socket(cpu: dict) -> str:
    return cpu['Socket'][len('Socket '):]  # this is very error-prone
    # TODO: make a proper socket class or sth


def get_further_cpu_data(link: str) -> dict:
    def get_td_text_by_th(th_name: str) -> str:
        nonlocal page
        return page.find('th', string=th_name).parent.find('td').text.strip()

    deep_data = {'pcie': None, 'ram': None}

    page = BeautifulSoup(request_get_v2(link).text, features='html.parser')

    further_pcie = PCIe('Gen 0.0 x0')
    pcie_string = get_td_text_by_th('PCI-Express:')
    pcie_list = pcie_string[0: pcie_string.find('(')].split(', ')
    further_pcie.lanes = int(pcie_list[-1].split()[0])
    further_pcie.generation = float(pcie_list[0].split()[-1])
    deep_data['pcie'] = further_pcie

    further_ram = RAM([])
    ddr_type = get_td_text_by_th('Memory Support:')
    further_ram.ddr_gen = int(ddr_type[-1])
    speed_mts = get_td_text_by_th('Rated Speed:')
    further_ram.speed_mhz = int(speed_mts.split()[0])
    deep_data['ram'] = further_ram

    return deep_data


def get_gpu_tdp(gpu_link: str, error_count: int = 0) -> int:
    response = request_get_v2(gpu_link)
    page = BeautifulSoup(response.text, features='html.parser')
    return int(page.find('dt', string='TDP').parent.find('dd').text.split()[0])


if __name__ == '__main__':
    # print(get_gpu_tdp('https://www.techpowerup.com/gpu-specs/radeon-rx-7600-xt.c4190'))
    print(get_further_cpu_data('https://www.techpowerup.com/cpu-specs/ryzen-5-3600.c2132'))
