import re
from datetime import datetime
from pydoc import pager

from bs4 import BeautifulSoup

from .decorators import login_required
from .utils.constants import BASE_URL, RESULT_CODES, SERVER_DOWN_MSG
from .utils.helpers import bold, get_session, print_inverse_table, print_table


def get_description(problem_code, contest_code=None):
    """
    :desc: Retrieves a particular problem description.
    :param: `problem_code` Code of the problem.
    :return: `str` [description / Not Found / Server down]
    """

    session = get_session()

    url = BASE_URL
    if contest_code is not None:
        url += '/' + contest_code
    url += '/problems/' + problem_code

    req_obj = session.get(url)

    if req_obj.status_code == 200:
        problem_html = req_obj.text
        soup = BeautifulSoup(problem_html, 'html.parser')
        if soup.find(id='problem-code'):
            content = soup.find_all('div', class_='content')[1]
            content.find_all('h3')[0].extract()
            content.find_all('h3')[0].extract()
            print(bold('Problem Description: '))
            pager(content.text)
            print(content.text)
            print('\n' + bold('Problem Info: '))
            print_inverse_table(str(soup.find_all('table')[2]))
        else:
            print('Problem not found.')
            if contest_code is None:
                print('Maybe, the problem exists only in the contest.\n'
                      'Add "--search <contest code>" to search in the contest '
                      'specific problems.')

    elif req_obj.status_code == 503:
        print(SERVER_DOWN_MSG)


def get_form_token(problem_submit_html):
    """
    :desc: Retrieves problem submission form token.
    :param: `problem_submit_html` HTML text containing problem submission form.
    :return: `str` form token value
    """

    soup = BeautifulSoup(problem_submit_html, 'html.parser')
    form = soup.find('form', id='problem-submission')
    return form.find('input', id='edit-problem-submission-form-token')['value']


def get_error_table(status_code):
    """
    :desc: Retrieves error status table.
    :param: `status_code` Status code of the submitted problem.
    :return: `str` error status table
    """

    session = get_session()
    req_obj = session.get(BASE_URL + '/error_status_table/' + status_code)
    if req_obj.status_code == 200:
        return req_obj.text

    return None


def get_compilation_error(status_code):
    """
    :desc: Retrieves compilation error text.
    :param: `status_code` Status code of the submitted problem.
    :return: `str` Compilation error text.
    """

    session = get_session()
    req_obj = session.get(BASE_URL + '/view/error/' + status_code)

    if req_obj.status_code == 200:
        soup = BeautifulSoup(req_obj.text, 'html.parser')
        return soup.find('div', class_='cc-error-txt').text

    if req_obj.status_code == 503:
        return SERVER_DOWN_MSG

    return ''


def get_language_code(problem_submit_html, language):
    """
    :desc: Retrieves language code.
    :param: `problem_submit_html` HTML text containing problem submission form.
            `language` Language Name (eg. Python3, C++, etc.)
    :return: `str` Language code.
    """

    soup = BeautifulSoup(problem_submit_html, 'html.parser')
    form = soup.find('form', id='problem-submission')
    languages_dropdown = form.find('select', id='edit-language')
    language_options = languages_dropdown.find_all('option')

    for option in language_options:
        if language.lower() + '(' in option.text.lower():
            return option['value']


@login_required
def submit_problem(problem_code, solution_file, language):
    """
    :desc: Submits the problem.
    :param: `problem_code` Code of the problem.
            `solution_file` Path of the solution file.
            `language` Language Name (eg. Python3, C++, etc.)
    :return: None
    """

    session = get_session()
    req_obj = session.get(BASE_URL + '/submit/' + problem_code)

    if req_obj.status_code == 200:
        form_token = get_form_token(req_obj.text)
        language_code = get_language_code(req_obj.text, language)
    elif req_obj.status_code == 503:
        print(SERVER_DOWN_MSG)
        return

    try:
        solution_file_obj = open(solution_file)
    except IOError:
        print('Solution file not found. Please provide a valid path.')

    post_data = {
        'language': language_code,
        'problem_code': problem_code,
        'form_id': 'problem_submission',
        'form_token': form_token,
    }
    post_files = {'files[sourcefile]': solution_file_obj}

    req_obj = session.post(BASE_URL + '/submit/' + problem_code, data=post_data, files=post_files)
    if req_obj.status_code == 200:
        print('Problem Submitted...')
        print('Running code...\n')

        status_code = req_obj.url.split('/')[-1]

        while True:
            status_req = session.get(BASE_URL + '/get_submission_status/' + status_code)
            try:
                status_json = status_req.json()
            except ValueError:
                continue
            result_code = status_json['result_code']

            if result_code != 'wait':
                if result_code == 'compile':
                    print(u'Compilation error.\n{0}'.format(get_compilation_error(status_code)))
                elif result_code == 'runtime':
                    print(u'Runtime error. {0}\n'.format(status_json['signal']))
                elif result_code == 'wrong':
                    print('Wrong answer\n')
                elif result_code == 'accepted':
                    print('Correct answer\n')

                print_table(get_error_table(status_code))
                break
    elif req_obj.status_code == 503:
        print(SERVER_DOWN_MSG)


def search_problems(search_type):
    """
    :desc: Retrieves problems of the specific type.
    :param: `search_type` 'school'/ 'easy'/ 'medium'/ 'hard'/ 'challenge'/ 'extcontest'
            / contest code (eg: OCT17, nov16, etc.)
    """

    session = get_session()
    search_types = ['school', 'easy', 'medium', 'hard', 'challenge', 'extcontest']

    is_contest = False
    if search_type.lower() in search_types:
        search_url = BASE_URL + '/problems/' + search_type.lower()
    else:
        search_url = BASE_URL + '/' + search_type.upper()
        is_contest = True

    req_obj = session.get(search_url)
    if req_obj.status_code == 200:
        soup = BeautifulSoup(req_obj.text, 'html.parser')
        table_html = str(soup.find_all('table')[1])
        print_table(table_html)

        if is_contest:
            contest_timer_block = soup.find_all('div', attrs={'class': 'rounded-block'})[0]
            timer_calc_script = contest_timer_block.find_all('script')

            if timer_calc_script:
                script_text = timer_calc_script[0].text
                end_date_str = re.search(r'new Date\("([a-zA-Z0-9 ,:]*)"\)', script_text).group(1)
                end_date_obj = datetime.strptime(end_date_str, '%B %d, %Y %H:%M:%S')
                now = datetime.now()
                diff = end_date_obj - now

                days = str(diff.days)
                hours = str(diff.seconds // 3600)
                minutes = str((diff.seconds % 3600) // 60)
                seconds = str((diff.seconds % 3600) % 60)

                time_left_text = bold('Contest ends in ') + days + ' days, ' + hours + ' hours, ' +\
                    minutes + ' minutes, ' + seconds + ' seconds.'
            else:
                time_left_text = bold('Contest ended.')

            print(time_left_text)

    elif req_obj.status_code == 503:
        print(SERVER_DOWN_MSG)


def get_contests():
    """
    :desc: Retrieves contests.
    """

    session = get_session()
    req_obj = session.get(BASE_URL + '/contests')

    if req_obj.status_code == 200:
        soup = BeautifulSoup(req_obj.text, 'html.parser')
        tables = soup.find_all('table')
        labels = ['Present', 'Future', 'Past']

        for i in range(1, 4):
            print(bold(labels[i-1] + ' Contests:\n'))
            print_table(str(tables[i]))
            print('\n')
    elif req_obj.status_code == 503:
        print(SERVER_DOWN_MSG)


def get_solutions(problem_code, page, language, result, username):
    """
    :desc: Retrieves solutions list of a problem.
    :param: `problem_code` Code of the problem.
            `page` Page Number
    """

    session = get_session()
    params = {'page': page - 1} if page != 1 else {}

    if language:
        req_obj = session.get(BASE_URL + '/status/' + problem_code.upper())
        soup = BeautifulSoup(req_obj.text, 'html.parser')
        lang_dropdown = soup.find('select', id='language')
        options = lang_dropdown.find_all('option')

        for option in options:
            if language.upper() == option.text.strip().upper():
                params['language'] = option['value']
                break
    if result:
        params['status'] = RESULT_CODES[result.upper()]
    if username:
        params['handle'] = username

    req_obj = session.get(BASE_URL + '/status/' + problem_code.upper(), params=params)

    if req_obj.status_code == 200:
        if 'SUBMISSIONS FOR ' in req_obj.text:
            soup = BeautifulSoup(req_obj.text, 'html.parser')
            solution_table = soup.find_all('table')[2]
            page_info = soup.find('div', attrs={'class': 'pageinfo'})

            rows = solution_table.find_all('tr')
            headings = rows[0].find_all('th')
            headings[-1].extract()

            for row in rows[1:]:
                cols = row.find_all('td')
                cols[-1].extract()

            print_table(str(solution_table))
            if page_info:
                print('\nPage: ' + page_info.text)
        else:
            print('Invalid Problem Code.')
    elif req_obj.status_code == 503:
        print(SERVER_DOWN_MSG)


def get_solution(solution_code):
    """
    :desc: Retrieves a solution
    :param: `solution_code` Code of the solution.
    """

    session = get_session(fake_browser=True)
    req_obj = session.get(BASE_URL + '/viewsolution/' + solution_code)

    if req_obj.status_code == 200:
        if 'Solution: ' + solution_code in req_obj.text:
            soup = BeautifulSoup(req_obj.text, 'html.parser')

            ol = soup.find('ol')
            lis = ol.find_all('li')
            status_table = soup.find('table', attrs={'class': 'status-table'})

            code = ''
            for li in lis:
                code += li.text + '\n'

            print('\n' + bold('Solution:') + '\n')
            print(code)
            print('\n' + bold('Submission Info:') + '\n')
            print_table(str(status_table))
        else:
            print('Invalid Solution Code.')
    elif req_obj.status_code == 503:
        print(SERVER_DOWN_MSG)
