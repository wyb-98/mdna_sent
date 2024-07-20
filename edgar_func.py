import pandas as pd
import requests
import time
from bs4 import BeautifulSoup
import re

class EmptyDataFrameError(Exception):
    pass

def get_company_basics(user_header):
    '''
    Lists the basic information of publically traded companies, via edgar.  

    Args:
        user_header (dict): {user_agent (str): email (str)}

    Returns:
        DataFrame: contains basic company info
            cik_str (str): company cik number
            ticker (str): company ticker
            title (str): company title
    '''
    # get all companies data
    tickers = requests.get("https://www.sec.gov/files/company_tickers.json",headers=user_header)
    time.sleep(0.2)

    # dictionary to dataframe
    output = pd.DataFrame.from_dict(tickers.json(), orient='index')
    # add leading zeros to CIK
    output['cik_str'] = output['cik_str'].astype(str).str.zfill(10)

    return output



def get_form_data(cik: str, user_header: dict, form_type: str) -> pd.DataFrame:
    '''
    Takes cik number and form type to output the recent filing data of a given company

    Args:
        cik (str): target companies cik number
        user_header (dict): {user_agent (str): email (str)}
        form_type (str): target financial form

    Returns:
        DataFrame: contains information about forms that match the user specifications, including
            accessionNumber (str): forms accession number
            filingDate (str): forms filing date
            form (str): the form type (10-Q, 20-F, etc.)
    '''

    #requesting form list from edgar
    r1 = requests.get(f'https://data.sec.gov/submissions/CIK{cik}.json',headers=user_header)

    #parsing json for recent filing data, converting to dataframe
    d = r1.json()['filings']['recent']
    output = pd.DataFrame.from_dict(d)

    #filtering by form type
    output = output[output.form == form_type]
    #sort by recency
    output = output.sort_values(by=['reportDate'], ascending= False)

    output['accessionNumber'] = output['accessionNumber'].replace(to_replace= r'-', value='', regex= True)
    
    output.rename(columns= {'accessionNumber': 'accession_number', 'primaryDocument': 'doc_extension'}, inplace= True)
    
    return output



def attribute_across_filings(cik: str, attribute: str, user_header: dict, form_type = '10-K', standard='us-gaap', currency='USD') -> pd.DataFrame:
    '''
    Takes an attribute (Revenue, PPE, etc.) found on financial documentation (10-Q, 20-F, etc.), and outputs all values of that attribute across time

    Args:
        cik (str): target companies cik number
        attribute (str): target attribute
        user_header (dict): {user_agent (str): email (str)}
        form_type (str): target financial form
        standard (str): accounting standard used by target company ('us-gaap', 'ifrs-full', etc.)
        currency (str): currency value of the attribute ('USD', 'TWD', etc.)

    Returns:
        DataFrame: contains information about forms that match the user specifications, including
            end (str): end date of the form
            val (numpy.int64): value of the chosen attribute on the form
    '''
    # get company concept data
    r = requests.get(f'https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/{standard}/{attribute}.json', headers=user_header)
    time.sleep(0.2)

    # get all filings data 
    output = pd.DataFrame.from_dict((r.json()['units'][currency]))

    # form type (10-K, 10-Q, 20-F, etc.)
    output = output[output.form == form_type]
    output = output.reset_index(drop=True)

    # raise error if df is empty
    if output.empty:
        raise EmptyDataFrameError()
    
    #prune data ??? need to check
    #output = output[output['frame'].notna()]
    
    return output



def extract_mdna(cik: str, accession_number: str, doc_extension: str, user_header: dict) -> str:
    '''
    Takes cik number, accession number, the target filings filename and extension, user header, and returns the Management Discussion

    Args:
        cik (str): target company cik
        accession_number (str): target forms accession number
        doc_extension (str): document name and extension
        user header(dict): {user_agent (str): email (str)}
        
    Returns:
        str: a string containing the text from the target form's Management Discussion and Analysis
    '''

    # this function is not optimal by any means, however, works for many companies, and required a low amount of XBRL know-how and/or Regex wizardry

    r = requests.get(f'https://www.sec.gov/Archives/edgar/data/{cik}/{accession_number}/{doc_extension}', headers=user_header)
    #working with the .text of a requests response is def not best practice, but works surprisingly well as a quick and dirty solution
    r = r.text
    soup = BeautifulSoup(r, features="xml")

    #remove tables
    for tag in soup.find_all("td"):
        tag.decompose()

    #removing \n
    string = soup.text.replace('\n', '')

    #regex to split text by item header
    item_header = re.compile('ITEM..\.', flags= re.I)
    data = item_header.split(string)

    df = pd.DataFrame(data, columns=['text'])

    #selecting item 2 i.e. the Management Discussion
    output = df.text.iloc[2]

    return output



def recent_mdna_text_by_company(cik: str, quarters: int, user_header: dict) -> pd.DataFrame:
    '''
    Takes cik number to return the text of the Management Discussion and Analysis of the last 4 quarters

    Args:
        cik (str): target company cik
        user header(dict): {user_agent (str): email (str)}
        
    Returns:
        DataFrame: contains filing date and the text of the MD&A
            end_date (str): end date of the form
            mdna (str): text of the MD&A for the target company and quarter
    '''

    #call the get_form_data function to get recent filings' name and information
    recent_form_data = get_form_data(user_header=user_header, cik = cik, form_type = '10-Q')

    #trim data to last x quarters
    recent_form_data = recent_form_data.iloc[:quarters]

    #extract the mdna from each row using .apply and the extract_mdna function
    recent_form_data['mdna'] = recent_form_data.apply(lambda x: extract_mdna(cik, x.accession_number, x.doc_extension, user_header), axis=1)

    #drop columns using names stored in list
    drop_columns = ['accession_number', 'filingDate', 'acceptanceDateTime', 'act', 'form', 'fileNumber', 'filmNumber','items', 'size', 'isXBRL', 'isInlineXBRL', 'doc_extension', 'primaryDocDescription']

    output = recent_form_data.drop(drop_columns, axis=1)
    output.reset_index(drop=True, inplace=True)
    output.rename(columns= {'reportDate': 'end_date'}, inplace= True)

    return output