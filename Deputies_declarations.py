# -*- coding: UTF-8 -*-
import urllib
import urllib2
import re
import codecs
import os
import sys
import time
from urllib import urlopen, urlretrieve
from bs4 import BeautifulSoup
from unidecode import unidecode


#Global constants
ENCODING = 'cp1251'

MAIN_URL = 'http://w1.c1.rada.gov.ua/pls/site2/fetch_mps?skl_id=8'
DECLARATION_LIST_URL_PATTERN = 'http://gapp.rada.gov.ua/declview/home/preview/%s'
DECLARATION_URL_PATTERN = 'http://gapp.rada.gov.ua%s'

FOLDER = 'c:/dec8/'
TSV_FILE = FOLDER + 'declarations.tsv'
CSV_FILE = FOLDER + 'list.csv'
NO_DEC_FILE = FOLDER + 'no_dec.csv'
NO_PAGE_FILE = FOLDER + 'no_page.csv'

FIELDS = ['person', 'position', 'declaration_year', 'source_type', 'point_code', 'point_title', 'declarer/family', 'content',
    'Sum1_property', 'Sum2_leasing', 'Name_of_country', 'Name_of_currency', 'Sum3_income_in_currency', 'block', 'additional_information', 'decl_section']

#Globals for catching exceptions
SLEEP_TIME = 5
TRIES = 2


def create_folder():
    '''
    Creates a folder if it doen't exist yet
    '''
    try:
        os.mkdir(FOLDER)
    except OSError:
        pass


def clear_files():
    open(TSV_FILE,'w').close()
    a = codecs.open(TSV_FILE,'a',encoding='utf-8')
    for field in FIELDS:
        a.write(field+'\t')
    a.write('\n')
    a.close()
    open(NO_DEC_FILE,'w').close()
    open(NO_PAGE_FILE,'w').close()
    open(CSV_FILE,'w').close()
    

def get_person_id(href):
    '''
    Gets person ID from person's link
    '''
    return href.split('/')[-1]


def get_page(FetchAddress):
    '''
    Fetches the url
    '''
    attempts = 0
    while (TRIES - attempts) > 1:
        req = urllib2.Request(FetchAddress, None)
        try:
            response = urllib2.urlopen(req)
        except IOError:
            time.sleep(SLEEP_TIME)
            attempts += 1
        except Exception:
            time.sleep(SLEEP_TIME)
            attempts += 1
        else:
            return response.read()
    return None


def get_people (url):
    '''
    Takes link on the page with deputies list and returns dictionary {id_person:link on deputy page, deputy's name}
    '''
    list_of_dep = {}
    page = get_page(url)
    if page!=None:
        soup = BeautifulSoup(page,fromEncoding=ENCODING)
    else:
        print "Can't get a list of deputies after " + str(TRIES) + " attempt(s). Possible, www.rada.gov.ua is not callable"
        return {}
    for link in soup.findAll('a', target="_blank"):
        list_of_dep[get_person_id(link['href'])] = [link['href'], link.string]
    return list_of_dep


def get_dec_year(dec_description):
    '''
    Takes string with daclaration's description and returns delaration's year
    '''
    return dec_description.split(' ')[4]


def get_dec_file_name(person_name, year):
    return person_name.split(' ')[0].replace("'","") + '_' + person_name.split(' ')[1][0] + person_name.split(' ')[2][0] + '_' + year + '.pdf'


def complete_content(p):
    '''
    Makes up string. Deletes tags, \r, \n.
    '''
    res = list()
    while '<' in p and p[:p.find('<')]:
        new_string = p[:p.find('<')].strip('\r\n').replace('\r\n','')
        res.append(new_string)
        p=p[p.find('>')+1:]
    return res


def form_decl_string(data_to_print):
    #check for empty content
    if data_to_print['point_title'] != '':
        result = ''
        for element in FIELDS:
            #print element
            if element in data_to_print:
                result += data_to_print[element] + '\t'
            else:
                result += '' + '\t'
        result = result[:-1]+'\n'
        a = codecs.open(TSV_FILE,'a',encoding='utf-8')
        a.write(result)
        a.close()
        

def parse_decl(page, person_name, year):
    res = list()
    soup = BeautifulSoup(page, fromEncoding='utf-8')
    declaration_div = soup.find('div', id="declaration")
    section_headers = declaration_div.findAll('h3',recursive=False)
    sections = declaration_div.findAll('div',recursive=False)

    # ------------- Parse section I -------------
    family_tab = sections[0].find('table')

    n = 0
    for i in family_tab.findAll('td'):
        n += 1
        if n%2 == 1:
            #remember name
            rel_title = i.decode_contents()
        else:
            #form the string
            rel_name = i.decode_contents()
            s = dict()
            s['person'] = person_name
            s['declaration_year'] = year
            s['point_title'] = u'Член сім`ї декларанта'
            s['content'] = rel_title + ', ' + rel_name
            s['decl_section'] = section_headers[0].decode_contents()
            form_decl_string(s)

    # ------------- Parse section II -------------
    income_tables = sections[1].findAll('table')

    # Section II.A
    s = dict()
    s['person'] = person_name
    s['declaration_year'] = year
    s['decl_section'] = section_headers[1].decode_contents()
    n = 0
    for i in income_tables[0].findAll('td'):
        n += 1
        if n%3 == 1:
            income_type = i.decode_contents()
        elif n%3 == 2:
            # personal income
            s['point_title'] = income_type
            s['declarer/family'] = u'декларант'
            s['content'] = i.decode_contents()
            if not s['content'].isdigit():
                s['additional_information'] = s['content']
            if s['content']:
                form_decl_string(s)
        else:
            # family income
            s['point_title'] = income_type
            s['declarer/family'] = u"сім'я"
            s['content'] = i.decode_contents()
            if not s['content'].isdigit():
                s['additional_information'] = s['content']
            if s['content']:
                form_decl_string(s)

    # Section II.B
    n = 0
    s['additional_information'] = ''
    for i in income_tables[1].findAll('td'):
        n += 1
        if n%3 == 1:
            income_country = i.decode_contents()
        elif n%3 == 2:
            currency_income = i.decode_contents()
        else:
            s['point_title'] = u"Одержані (нараховані) з джерел за межами України"
            s['declarer/family'] = u"декларант"
            s['content'] = i.decode_contents()
            if not i.decode_contents().isdigit():
                s['additional_information'] = i.decode_contents()
            s['Name_of_country'] = income_country
            s['Name_of_currency'] = currency_income.split(' ')[1]
            s['Sum3_income_in_currency'] = currency_income.split(' ')[0]
            if any([s['content'], s['Sum3_income_in_currency']]):
                form_decl_string(s)

    # Section II.V
    n = 0
    s['additional_information'] = ''
    for i in income_tables[2].findAll('td'):
        n += 1
        if n%3 == 1:
            income_country = i.decode_contents()
        elif n%3 == 2:
            currency_income = i.decode_contents()
        else:
            s['point_title'] = u"Одержані (нараховані) з джерел за межами України"
            s['declarer/family'] = u"сім'я"
            s['content'] = i.decode_contents()
            if not s['content']:
                s['additional_information'] = i.decode_contents()
            s['Name_of_country'] = income_country
            s['Name_of_currency'] = currency_income.split(' ')[1]
            s['Sum3_income_in_currency'] = currency_income.split(' ')[0]
            if any([s['content'], s['Sum3_income_in_currency']]):
                form_decl_string(s)

    # ------------- Parse section III -------------
    realestate_tables = sections[2].findAll('table')
    # Section III.A
    s = dict()
    s['person'] = person_name
    s['declaration_year'] = year
    s['decl_section'] = section_headers[2].decode_contents()
    n = 0
    for i in realestate_tables[0].findAll('td'):
        n += 1
        if n%4 == 1:
            realestate_type = i.decode_contents()
        elif n%4 == 2:
            square = complete_content(i.decode_contents())
        elif n%4 == 3:
            sum_property = complete_content(i.decode_contents())
        else:
            s['point_title'] = realestate_type
            s['declarer/family'] = u"декларант"
            sum2_leasing = complete_content(i.decode_contents())
            for e in range(len(square)):
                s['content'] = square[e]
                if not s['content'].isdigit():
                    s['additional_information'] = s['content']
                s['Sum1_property'] = sum_property[e]
                s['Sum2_leasing'] = sum2_leasing[e]
                if any([s['content'], s['Sum1_property'], s['Sum2_leasing']]):
                    form_decl_string(s)

    # Section III.B
    n = 0
    s['additional_information'] = ''
    s['Sum1_property'] = ''
    s['Sum2_leasing'] = ''
    for i in realestate_tables[1].findAll('td'):
        n += 1
        if n%2 == 1:
            realestate_type = i.decode_contents()
        else:
            s['point_title'] = realestate_type
            s['declarer/family'] = u"сім'я"
            content = complete_content(i.decode_contents())
            for item in content:
                s['content'] = item
                if not s['content'].isdigit():
                    s['additional_information'] = s['content']
                if s['content']:
                    form_decl_string(s)

    # ------------- Parse section IV -------------
    transport_tables = sections[3].findAll('table')
    
    # Section IV.A
    s = dict()
    s['person'] = person_name
    s['declaration_year'] = year
    s['decl_section'] = section_headers[3].decode_contents()
    n = 0
    for i in transport_tables[0].findAll('td'):
        n += 1
        if n%5 == 1:
            transport_name = i.decode_contents()
        elif n%5 == 2:
            transport_type = complete_content(i.decode_contents())
        elif n%5 == 3:
            transport_year = complete_content(i.decode_contents())
        elif n%5 == 4:
            sum_property = complete_content(i.decode_contents())
        else:
            s['point_title'] = transport_name
            s['declarer/family'] = u"декларант"
            sum2_leasing = complete_content(i.decode_contents())
            content = [transport_type[i]+', '+transport_year[i]+u'р.в.' for i in range(0, len(transport_type))]
            for e in range(len(content)):
                s['content'] = content[e].strip()
                s['Sum1_property'] = sum_property[e]
                s['Sum2_leasing'] = sum2_leasing[e]
                if any([s['content'], s['Sum1_property'], s['Sum2_leasing']]):
                    form_decl_string(s)

    # Section IV.B
    n = 0
    s['Sum1_property'] = ''
    s['Sum2_leasing'] = ''
    for i in transport_tables[1].findAll('td'):
        n += 1
        if n%3 == 1:
            transport_name = i.decode_contents()
        elif n%3 == 2:
            transport_type = complete_content(i.decode_contents())
        else:
            transport_year = complete_content(i.decode_contents())
            s['point_title'] = transport_name
            s['declarer/family'] = u"сім'я"
            content = [transport_type[i]+', '+transport_year[i]+u'р.в.' for i in range(0, len(transport_type))]
            for item in content:
                s['content'] = item.strip()
                if s['content']:
                    form_decl_string(s)
    
    # ------------- Parse section V -------------
    depostock_tables = sections[4].findAll('table')
    
    # Section V.A
    s = dict()
    s['person'] = person_name
    s['declaration_year'] = year
    s['decl_section'] = section_headers[4].decode_contents()
    n = 0
    for i in depostock_tables[0].findAll('td'):
        n += 1
        if n%3 == 1:
            depostock_type = i.decode_contents()
        elif n%3 == 2:
            s['declarer/family'] = u"декларант"
            s['point_title'] = depostock_type
            if u'та' in i.decode_contents():
                s['content'] = ';'.join(re.compile('\d+').findall(i.decode_contents()))
                s['additional_information'] = s['content']
                form_decl_string(s)
            else:
                depostock_sum = complete_content(i.decode_contents())
                for item in depostock_sum:
                    if item!='':
                        s['content'] = item
                        if not s['content'].isdigit():
                            s['additional_information'] = s['content']
                        form_decl_string(s)
        else:
            s['point_title'] = depostock_type + u'закордоном'
            if u'та' in i.decode_contents():
                s['content'] = ';'.join(re.compile('\d+').findall(i.decode_contents()))
                s['additional_information'] = s['content']
                form_decl_string(s)
            else:
                depostock_sum_foreign = complete_content(i.decode_contents())
                for item in depostock_sum_foreign:
                    if item!='':
                        s['content'] = item
                        if not s['content'].isdigit():
                            s['additional_information'] = s['content']
                        form_decl_string(s)

    # Section V.B
    s = dict()
    s['person'] = person_name
    s['declaration_year'] = year
    s['decl_section'] = section_headers[4].decode_contents()
    n = 0
    for i in depostock_tables[1].findAll('td'):
        n += 1
        if n%3 == 1:
            depostock_type = i.decode_contents()
        elif n%3 == 2:
            s['declarer/family'] = u"сім'я"
            s['point_title'] = depostock_type
            if u'та' in i.decode_contents():
                s['content'] = ';'.join(re.compile('\d+').findall(i.decode_contents()))
                s['additional_information'] = s['content']
                form_decl_string(s)
            else:
                depostock_sum = complete_content(i.decode_contents())
                for item in depostock_sum:
                    if item!='':
                        s['content'] = item
                        if not s['content'].isdigit():
                            s['additional_information'] = s['content']
                        form_decl_string(s)
        else:
            s['point_title'] = depostock_type
            if u'та' in i.decode_contents():
                s['content'] = ';'.join(re.compile('\d+').findall(i.decode_contents()))
                s['additional_information'] = s['content']
                form_decl_string(s)
            else:
                depostock_sum_foreign = complete_content(i.decode_contents())
                for item in depostock_sum_foreign:
                    if item!='':
                        s['content'] = item
                        if not s['content'].isdigit():
                            s['additional_information'] = s['content']
                        form_decl_string(s)

    # ------------- Parse section VI -------------
            
    finliability_tables = sections[5].findAll('table')
    
    # Section VI.A
    s = dict()
    s['person'] = person_name
    s['declaration_year'] = year
    s['decl_section'] = section_headers[5].decode_contents()
    n = 0
    for i in finliability_tables[0].findAll('td'):
        n += 1
        if n%3 == 1:
            finliability_type = i.decode_contents()
        elif n%3 == 2:
            finliability_sum = complete_content(i.decode_contents())
        else:
            s['declarer/family'] = u"декларант"
            finliability_sum_foreign = complete_content(i.decode_contents())
            if any(finliability_sum):
                s['point_title'] = finliability_type
                for item in finliability_sum:
                    if u'та' in item:
                        s['content'] = ';'.join(re.compile('\d+.*\d+').findAll(item))
                        s['additional_information'] = s['content']
                    else:
                        s['content'] = item
                        if not s['content'].isdigit():
                            s['additional_information'] = s['content']
                    form_decl_string(s)
            if any(finliability_sum_foreign):
                s['point_title'] = finliability_type + u' закордоном'
                for item in finliability_sum:
                    if u'та' in item:
                        s['content'] = ';'.join(re.compile('\d+.*\d+').findAll(item))
                        s['additional_information'] = s['content']
                    else:
                        s['content'] = item
                        if not s['content'].isdigit():
                            s['additional_information'] = s['content']
                    form_decl_string(s)
            
    # Section VI.B
    s = dict()
    s['additional_information'] = ''
    s['person'] = person_name
    s['declaration_year'] = year
    s['decl_section'] = section_headers[5].decode_contents()
    n = 0
    for i in finliability_tables[1].findAll('td'):
        n += 1
        if n%3 == 1:
            finliability_type = i.decode_contents()
        elif n%3 == 2:
            finliability_sum = complete_content(i.decode_contents())
        else:
            s['declarer/family'] = u"сім'я"
            finliability_sum_foreign = complete_content(i.decode_contents())
            if finliability_sum[0]:
                s['point_title'] = finliability_type
                s['content'] = ';'.join(finliability_sum)
                if not s['content'].isdigit():
                    s['additional_information'] = s['content']
                form_decl_string(s)
            if finliability_sum_foreign[0]:
                s['point_title'] = finliability_type + u' закордоном'
                s['content'] = ';'.join(finliability_sum_foreign)
                if not s['content'].isdigit():
                    s['additional_information'] = s['content']
                form_decl_string(s)


def main(url):
    '''
    The main procedure. Downloads declarations, complete CSV_FILE, NO_DEC_FILE, NO_PAGE_FILE
    '''
    people_list = get_people(url)
    for person_id in people_list:
        time.sleep(SLEEP_TIME)
        page = get_page(DECLARATION_LIST_URL_PATTERN % person_id)
        print DECLARATION_LIST_URL_PATTERN % person_id, 'is in process'
        # Check is a deputy's page callable
        if page!=None:
            print 'get page', DECLARATION_LIST_URL_PATTERN % person_id
            soup = BeautifulSoup(page,fromEncoding=ENCODING)
            # declarations = [[link_on_declaration1, year1],[link_on_declaration2, year2]...]
            declarations = [[i['href'],get_dec_year(i.string)] for i in soup.findAll('a', href=re.compile("^/declview+"))]
            for declaration in declarations:
                decl_page = get_page(DECLARATION_URL_PATTERN % declaration[0])
                if decl_page != None:
                    print 'get page', DECLARATION_URL_PATTERN % declaration[0]
                    if 'GetFile' in declaration[0]:
                        #download declaration
                        urlretrieve (DECLARATION_URL_PATTERN % declaration[0], FOLDER + get_dec_file_name(unidecode(people_list[person_id][1]),declaration[1]))
                        #write deputy in csv_file
                        a = codecs.open(CSV_FILE,'a',encoding='cp1251')
                        a.write(people_list[person_id][1] + "," + declaration[1] + "," + "pdf" + '\n')
                        a.close()
                    else:
                        a = codecs.open(CSV_FILE,'a',encoding='cp1251')
                        a.write(people_list[person_id][1] + "," + declaration[1] + "," + "data" + '\n')
                        a.close()
                        parse_decl(decl_page, people_list[person_id][1],declaration[1])
                else:
                    b = codecs.open(NO_DEC_FILE,'a',encoding='cp1251')
                    b.write(people_list[person_id][1] + "," + declaration[1] + '\n')
                    b.close()
        else:
            a = codecs.open(NO_PAGE_FILE,'a',encoding='cp1251')
            a.write(people_list[person_id][1] + '\n')
            a.close()


create_folder()
clear_files()
main(MAIN_URL)
