#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import urllib.request, urllib.parse, urllib.error
import urllib.request, urllib.error, urllib.parse
import re
import codecs
import os
import sys
import time
import socket
import errno
import csv
from urllib.request import urlopen, urlretrieve
from copy import copy

from bs4 import BeautifulSoup
from unidecode import unidecode
from pyquery import PyQuery as pq

# Global constants
ENCODING = 'cp1251'

MAIN_URL = 'http://w1.c1.rada.gov.ua/pls/site2/fetch_mps?skl_id=9'
DECLARATION_LIST_URL_PATTERN = 'http://gapp.rada.gov.ua/declview/home/preview/%s'
DECLARATION_URL_PATTERN = 'http://gapp.rada.gov.ua%s'

FOLDER = './decl_8_output/'
TSV_FILE = FOLDER + 'declarations.tsv'
CSV_FILE = FOLDER + 'list.csv'
NO_DEC_FILE = FOLDER + 'no_dec.csv'
NO_PAGE_FILE = FOLDER + 'no_page.csv'

FIELDS = ['person', 'position', 'declaration_year', 'source_type', 'point_code', 'point_title', 'declarer/family', 'content',
          'Sum1_property', 'Sum2_leasing', 'Name_of_country', 'Name_of_currency', 'Sum3_income_in_currency', 'block', 'additional_information', 'decl_section']

# Globals for catching exceptions
SLEEP_TIME = 4
TRIES = 2

VALUES_ORDER = ['декларант', 'сім\'я']


def create_folder():
    '''
    Creates a folder if it doesn't exist yet
    '''
    try:
        os.mkdir(FOLDER)
    except OSError:
        pass


def clear_files():
    open(TSV_FILE, 'w').close()
    a = codecs.open(TSV_FILE, 'a', encoding='utf-8')
    for field in FIELDS:
        a.write(field + '\t')
    a.write('\n')
    a.close()
    open(NO_DEC_FILE, 'w').close()
    open(NO_PAGE_FILE, 'w').close()
    open(CSV_FILE, 'w').close()


def get_person_id(href):
    '''
    Gets person ID from person's link
    '''
    return href.split('/')[-1]


def get_page(fetch_address):
    '''
    Fetches the url
    '''
    print(fetch_address)
    attempts = 0
    while (TRIES - attempts) > 1:
        attempts += 1
        req = urllib.request.Request(fetch_address, None)
        try:
            response = urllib.request.urlopen(req)
        except IOError:
            time.sleep(SLEEP_TIME)
        except Exception:
            time.sleep(SLEEP_TIME)
        else:
            return response.read()
    return None


def get_people(url):
    '''
    Takes link on the page with deputies list and returns dictionary {id_person:link on deputy page, deputy's name}
    '''
    list_of_dep = {}
    page = get_page(url)

    if page is not None:
        pageq = pq(page.decode(ENCODING))
        links = pageq("a[target='_blank']")
        print('Total links found: ', len(links))
    else:
        print("Can't get a list of deputies after " + str(TRIES) + " attempt(s). Possible, www.rada.gov.ua is not callable")
        return {}

    for link in links:
        linkq = pq(link)
        href = linkq.attr('href')
        deputy_name = linkq.text()
        list_of_dep[get_person_id(href)] = [href, deputy_name]

    return list_of_dep


def get_dec_year(dec_description):
    '''
    Takes string with daclaration's description and returns delaration's year
    '''
    return dec_description.split(' ')[4]


def get_dec_file_name(person_name, year):
    return person_name.split(' ')[0].replace("'", "") + '_' + person_name.split(' ')[1][0] + person_name.split(' ')[2][0] + '_' + year + '.pdf'


def complete_content(p):
    '''
    Makes up string. Deletes tags, \r, \n.
    '''
    res = list()
    while '<' in p and p[:p.find('<')]:
        new_string = p[:p.find('<')].strip('\r\n').replace('\r\n', '')
        res.append(new_string)
        p = p[p.find('>') + 1:]
    return res


def write_decl_row(row_dict, writer):
    # check for empty content
    if row_dict['point_title'] != '':
        row = []
        for field in FIELDS:
            if field in row_dict:
                row.append(row_dict[field])
            else:
                row.append("")

        writer.writerow(row)


def write_decl_rows(rows, writer):
    for row in rows:
        write_decl_row(row, writer)


def parse_decl(page, person_name, year):
    res = list()
    soup = BeautifulSoup(page)
    declaration_div = soup.find('div', id="declaration")
    section_headers = declaration_div.findAll('h3', recursive=False)
    sections = declaration_div.findAll('div', recursive=False)

    filehandler = codecs.open(TSV_FILE, 'a', encoding='utf-8')
    writer = csv.writer(filehandler, delimiter='\t')

    # ------------- Parse section I -------------
    family_tab = sections[0].find('table')

    n = 0
    for i in family_tab.findAll('td'):
        n += 1
        if n % 2 == 1:
            # remember name
            rel_title = i.decode_contents()
        else:
            # form the row
            rel_name = i.decode_contents()
            row = dict()
            row['person'] = person_name
            row['declaration_year'] = year
            row['point_title'] = 'Член сім`ї декларанта'
            row['content'] = rel_title + ', ' + rel_name
            row['decl_section'] = section_headers[0].decode_contents()
            write_decl_row(row, writer)

    # ------------- Parse section II -------------
    income_tables = sections[1].findAll('table')

    # Section II.A
    row = dict()
    row['person'] = person_name
    row['declaration_year'] = year
    row['decl_section'] = section_headers[1].decode_contents()

    rows = list()
    trs = income_tables[0].findAll('tr')
    for tr in trs:
        tds = tr.findAll('td')
        if len(tds) == 3:
            income_type, personal_value, family_value = [
                td.get_text() for td in tds
            ]
            values_order = copy(VALUES_ORDER)
            for value in (personal_value, family_value):
                current_row = copy(row)
                current_row['point_title'] = income_type
                current_row['declarer/family'] = values_order.pop(0)
                current_row['content'] = value
                if not current_row['content'].isdigit():
                    current_row['additional_information'] = current_row['content']
                if current_row['content']:
                    rows.append(current_row)
        elif len(tds) == 1:
            td = tds[0]
            if 'colspan' in td.attrs and td.attrs['colspan'] == "3":
                rows[-1]['additional_information'] = td.get_text()
        else:
            pass
    write_decl_rows(rows, writer)

    # Section II.B
    n = 0
    row['additional_information'] = ''
    for i in income_tables[1].findAll('td'):
        n += 1
        if n % 3 == 1:
            income_country = i.decode_contents()
        elif n % 3 == 2:
            currency_income = i.decode_contents()
        else:
            row['point_title'] = "Одержані (нараховані) з джерел за межами України"
            row['declarer/family'] = "декларант"
            row['content'] = i.decode_contents()
            if not i.decode_contents().isdigit():
                row['additional_information'] = i.decode_contents()
            row['Name_of_country'] = income_country
            try:
                row['Name_of_currency'] = currency_income.split(' ')[1]
            except IndexError:
                row['Name_of_currency'] = 'назву валюти не зазначено'
            row['Sum3_income_in_currency'] = currency_income.split(' ')[0]
            if any([row['content'], row['Sum3_income_in_currency']]):
                write_decl_row(row, writer)

    # Section II.V
    n = 0
    row['additional_information'] = ''
    for i in income_tables[2].findAll('td'):
        n += 1
        if n % 3 == 1:
            income_country = i.decode_contents()
        elif n % 3 == 2:
            currency_income = i.decode_contents()
        else:
            row['point_title'] = "Одержані (нараховані) з джерел за межами України"
            row['declarer/family'] = "сім'я"
            row['content'] = i.decode_contents()
            if not row['content']:
                row['additional_information'] = i.decode_contents()
            row['Name_of_country'] = income_country
            try:
                row['Name_of_currency'] = currency_income.split(' ')[1]
            except IndexError:
                row['Name_of_currency'] = 'назву валюти не зазначено'
            row['Sum3_income_in_currency'] = currency_income.split(' ')[0]
            if any([row['content'], row['Sum3_income_in_currency']]):
                write_decl_row(row, writer)

    # ------------- Parse section III -------------
    realestate_tables = sections[2].findAll('table')
    # Section III.A
    row = dict()
    row['person'] = person_name
    row['declaration_year'] = year
    row['decl_section'] = section_headers[2].decode_contents()
    n = 0
    for i in realestate_tables[0].findAll('td'):
        n += 1
        if n % 4 == 1:
            realestate_type = i.decode_contents()
        elif n % 4 == 2:
            square = complete_content(i.decode_contents())
        elif n % 4 == 3:
            sum_property = complete_content(i.decode_contents())
        else:
            row['point_title'] = realestate_type
            row['declarer/family'] = "декларант"
            sum2_leasing = complete_content(i.decode_contents())
            for e in range(len(square)):
                row['content'] = square[e]
                if not row['content'].isdigit():
                    row['additional_information'] = row['content']
                row['Sum1_property'] = sum_property[e]
                row['Sum2_leasing'] = sum2_leasing[e]
                if any([row['content'], row['Sum1_property'], row['Sum2_leasing']]):
                    write_decl_row(row, writer)

    # Section III.B
    n = 0
    row['additional_information'] = ''
    row['Sum1_property'] = ''
    row['Sum2_leasing'] = ''
    for i in realestate_tables[1].findAll('td'):
        n += 1
        if n % 2 == 1:
            realestate_type = i.decode_contents()
        else:
            row['point_title'] = realestate_type
            row['declarer/family'] = "сім'я"
            content = complete_content(i.decode_contents())
            for item in content:
                row['content'] = item
                if not row['content'].isdigit():
                    row['additional_information'] = row['content']
                if row['content']:
                    write_decl_row(row, writer)

    # ------------- Parse section IV -------------
    transport_tables = sections[3].findAll('table')

    # Section IV.A
    row = dict()
    row['person'] = person_name
    row['declaration_year'] = year
    row['decl_section'] = section_headers[3].decode_contents()
    n = 0
    for i in transport_tables[0].findAll('td'):
        n += 1
        if n % 5 == 1:
            transport_name = i.decode_contents()
        elif n % 5 == 2:
            transport_type = complete_content(i.decode_contents())
        elif n % 5 == 3:
            transport_year = complete_content(i.decode_contents())
        elif n % 5 == 4:
            sum_property = complete_content(i.decode_contents())
        else:
            row['point_title'] = transport_name
            row['declarer/family'] = "декларант"
            sum2_leasing = complete_content(i.decode_contents())
            content = [transport_type[i] + ', ' + transport_year[i] +
                       'р.в.' for i in range(0, len(transport_type))]
            for e in range(len(content)):
                row['content'] = content[e].strip()
                row['Sum1_property'] = sum_property[e]
                row['Sum2_leasing'] = sum2_leasing[e]
                if any([row['content'], row['Sum1_property'], row['Sum2_leasing']]):
                    write_decl_row(row, writer)

    # Section IV.B
    n = 0
    row['Sum1_property'] = ''
    row['Sum2_leasing'] = ''
    for i in transport_tables[1].findAll('td'):
        n += 1
        if n % 3 == 1:
            transport_name = i.decode_contents()
        elif n % 3 == 2:
            transport_type = complete_content(i.decode_contents())
        else:
            transport_year = complete_content(i.decode_contents())
            row['point_title'] = transport_name
            row['declarer/family'] = "сім'я"
            content = [transport_type[i] + ', ' + transport_year[i] +
                       'р.в.' for i in range(0, len(transport_type))]
            for item in content:
                row['content'] = item.strip()
                if row['content']:
                    write_decl_row(row, writer)

    # ------------- Parse section V -------------
    depostock_tables = sections[4].findAll('table')

    # Section V.A
    row = dict()
    row['person'] = person_name
    row['declaration_year'] = year
    row['decl_section'] = section_headers[4].decode_contents()
    n = 0
    for i in depostock_tables[0].findAll('td'):
        n += 1
        if n % 3 == 1:
            depostock_type = i.decode_contents()
        elif n % 3 == 2:
            row['declarer/family'] = "декларант"
            row['point_title'] = depostock_type
            if 'та' in i.decode_contents():
                row['content'] = ';'.join(
                    re.compile('\d+').findall(i.decode_contents()))
                row['additional_information'] = row['content']
                write_decl_row(row, writer)
            else:
                depostock_sum = complete_content(i.decode_contents())
                for item in depostock_sum:
                    if item != '':
                        row['content'] = item
                        if not row['content'].isdigit():
                            row['additional_information'] = row['content']
                        write_decl_row(row, writer)
        else:
            row['point_title'] = depostock_type + 'закордоном'
            if 'та' in i.decode_contents():
                row['content'] = ';'.join(
                    re.compile('\d+').findall(i.decode_contents()))
                row['additional_information'] = row['content']
                write_decl_row(row, writer)
            else:
                depostock_sum_foreign = complete_content(i.decode_contents())
                for item in depostock_sum_foreign:
                    if item != '':
                        row['content'] = item
                        if not row['content'].isdigit():
                            row['additional_information'] = row['content']
                        write_decl_row(row, writer)

    # Section V.B
    row = dict()
    row['person'] = person_name
    row['declaration_year'] = year
    row['decl_section'] = section_headers[4].decode_contents()
    n = 0
    for i in depostock_tables[1].findAll('td'):
        n += 1
        if n % 3 == 1:
            depostock_type = i.decode_contents()
        elif n % 3 == 2:
            row['declarer/family'] = "сім'я"
            row['point_title'] = depostock_type
            if 'та' in i.decode_contents():
                row['content'] = ';'.join(
                    re.compile('\d+').findall(i.decode_contents()))
                row['additional_information'] = row['content']
                write_decl_row(row, writer)
            else:
                depostock_sum = complete_content(i.decode_contents())
                for item in depostock_sum:
                    if item != '':
                        row['content'] = item
                        if not row['content'].isdigit():
                            row['additional_information'] = row['content']
                        write_decl_row(row, writer)
        else:
            row['point_title'] = depostock_type
            if 'та' in i.decode_contents():
                row['content'] = ';'.join(
                    re.compile('\d+').findall(i.decode_contents()))
                row['additional_information'] = row['content']
                write_decl_row(row, writer)
            else:
                depostock_sum_foreign = complete_content(i.decode_contents())
                for item in depostock_sum_foreign:
                    if item != '':
                        row['content'] = item
                        if not row['content'].isdigit():
                            row['additional_information'] = row['content']
                        write_decl_row(row, writer)

    # ------------- Parse section VI -------------

    finliability_tables = sections[5].findAll('table')

    # Section VI.A
    row = dict()
    row['person'] = person_name
    row['declaration_year'] = year
    row['decl_section'] = section_headers[5].decode_contents()
    n = 0
    for i in finliability_tables[0].findAll('td'):
        n += 1
        if n % 3 == 1:
            finliability_type = i.decode_contents()
        elif n % 3 == 2:
            finliability_sum = complete_content(i.decode_contents())
        else:
            row['declarer/family'] = "декларант"
            finliability_sum_foreign = complete_content(i.decode_contents())
            if any(finliability_sum):
                row['point_title'] = finliability_type
                for item in finliability_sum:
                    if ' та' in item:
                        row['content'] = ';'.join(
                            re.compile('\d+.*\d+').findall(item))
                        row['additional_information'] = row['content']
                    else:
                        row['content'] = item
                        if not row['content'].isdigit():
                            row['additional_information'] = row['content']
                    write_decl_row(row, writer)
            if any(finliability_sum_foreign):
                row['point_title'] = finliability_type + ' закордоном'
                for item in finliability_sum:
                    if 'та' in item:
                        row['content'] = ';'.join(
                            re.compile('\d+.*\d+').findall(item))
                        row['additional_information'] = row['content']
                    else:
                        row['content'] = item
                        if not row['content'].isdigit():
                            row['additional_information'] = row['content']
                    write_decl_row(row, writer)

    # Section VI.B
    row = dict()
    row['additional_information'] = ''
    row['person'] = person_name
    row['declaration_year'] = year
    row['decl_section'] = section_headers[5].decode_contents()
    n = 0
    for i in finliability_tables[1].findAll('td'):
        n += 1
        if n % 3 == 1:
            finliability_type = i.decode_contents()
        elif n % 3 == 2:
            finliability_sum = complete_content(i.decode_contents())
        else:
            row['declarer/family'] = "сім'я"
            finliability_sum_foreign = complete_content(i.decode_contents())
            if finliability_sum[0]:
                row['point_title'] = finliability_type
                row['content'] = ';'.join(finliability_sum)
                if not row['content'].isdigit():
                    row['additional_information'] = row['content']
                write_decl_row(row, writer)
            if finliability_sum_foreign[0]:
                row['point_title'] = finliability_type + ' закордоном'
                row['content'] = ';'.join(finliability_sum_foreign)
                if not row['content'].isdigit():
                    row['additional_information'] = row['content']
                write_decl_row(row, writer)

    filehandler.close()


def main(url):
    '''
    The main procedure. Downloads declarations, complete CSV_FILE, NO_DEC_FILE, NO_PAGE_FILE
    '''
    people_list = get_people(url)
    for person_id in people_list:
        print(people_list[person_id][1])
        time.sleep(SLEEP_TIME)
        page = get_page(DECLARATION_LIST_URL_PATTERN % person_id)
        #print(DECLARATION_LIST_URL_PATTERN % person_id, 'is in process')
        # Check is a deputy's page callable
        if page is not None:
            #print('get page', DECLARATION_LIST_URL_PATTERN % person_id)
            soup = BeautifulSoup(page)
            # declarations = [[link_on_declaration1,
            # year1],[link_on_declaration2, year2]...]
            declarations = [[i['href'], get_dec_year(i.string)] for i in soup.findAll(
                'a', href=re.compile("^/declview+"))]
            for declaration in declarations:
                decl_page = get_page(DECLARATION_URL_PATTERN % declaration[0])
                if decl_page is not None:
                    #print('get page', DECLARATION_URL_PATTERN % declaration[0])
                    if 'GetFile' in declaration[0]:
                        # download declaration
                        '''
                        try:
                            urlretrieve(DECLARATION_URL_PATTERN % declaration[0], FOLDER
                                        + get_dec_file_name(unidecode(people_list[person_id][1]), declaration[1]))
                        # except socket.error as error:
                        except:
                            b = codecs.open(
                                NO_DEC_FILE, 'a')
                            b.write(
                                people_list[person_id][1] + "," + declaration[1] + '\n')
                            b.close()

                        # write deputy in csv_file
                        a = codecs.open(CSV_FILE, 'a')
                        a.write(
                            people_list[person_id][1] + "," + declaration[1] + "," + "pdf" + '\n')
                        a.close()
                        '''
                    else:
                        a = codecs.open(CSV_FILE, 'a')
                        a.write(
                            people_list[person_id][1] + "," + declaration[1] + "," + "data" + '\n')
                        a.close()
                        parse_decl(
                            decl_page, people_list[person_id][1], declaration[1])
                else:
                    b = codecs.open(NO_DEC_FILE, 'a')
                    b.write(
                        people_list[person_id][1] + "," + declaration[1] + '\n')
                    b.close()
        else:
            a = codecs.open(NO_PAGE_FILE, 'a')
            a.write(people_list[person_id][1] + '\n')
            a.close()


create_folder()
clear_files()
main(MAIN_URL)
