"""Parse an apartments.com search result page and export to CSV."""

import csv
import json
import re
import sys
import datetime
import requests
from bs4 import BeautifulSoup

# Config parser was renamed in Python 3
try:
    import configparser
except ImportError:
    import ConfigParser as configparser

def create_csv(page_url, map_info, fname, pscores):
    """Create a CSV file with information that can be imported into ideal-engine"""

    # avoid the issue on Windows where there's an extra space every other line
    if sys.version_info[0] == 2:  # Not named on 2.6
        access = 'wb'
        kwargs = {}
    else:
        access = 'wt'
        kwargs = {'newline': ''}
    # open file for writing
    csv_file = open(fname, access, **kwargs)

    # write to CSV
    try:
        writer = csv.writer(csv_file)
        # this is the header (make sure it matches with the fields in
        # write_parsed_to_csv)
        header = ['Property Name','url', 'Contact', 'Address','G_map' ,'1bedroom','2bedroom','3bedroom',
                  'Rent', 'Monthly Fees', 'One Time Fees',
                  'Pet Policy',
                  'Parking', 'Gym', 'Kitchen',
                  'Amenities', 'Features', 'Living Space',
                  'Lease Info', 'Services',
                  'Property Info', 'Indoor Info', 'Outdoor Info',
                  'Description']
        # add the score fields if necessary
        if pscores:
            for i in range(len(header), 0, -1):
                header.insert(i, 5)
            # flag that we're importing with scores
            header[1] = 'score'
            header.append('modifier')
        # write the header
        writer.writerow(header)

        # parse current entire apartment list including pagination
        write_parsed_to_csv(page_url, map_info, writer, pscores)
    finally:
        csv_file.close()





def write_parsed_to_csv(page_url, map_info, writer, pscores):
    """Given the current page URL, extract the information from each apartment in the list"""

    # read the current page
    page = requests.get(page_url)
 
    # soupify the current page
    soup = BeautifulSoup(page.content, 'html.parser')
    soup.prettify()
    # only look in this region
    soup = soup.find('div', class_='placardContainer')

    # append the current apartments to the list
    for item in soup.find_all('article', class_='placard'):
        url = ''
        rent = ''
        contact = ''

        if item.find('a', class_='placardTitle') is None: continue
        url = item.find('a', class_='placardTitle').get('href')

        # get the rent and parse it to unicode
        obj = item.find('span', class_='altRentDisplay')
        if obj is not None:
            rent = obj.getText().strip()

        # get the phone number and parse it to unicode
        obj = item.find('div', class_='phone')
        if obj is not None:
            contact = obj.getText().strip()

        # get the other fields to write to the CSV
        fields = parse_apartment_information(url, map_info)

        # make this wiki markup
        fields['name'] = fields['name']
        fields['url']= url 
        fields['address'] = fields['address'] 
        fields['G_map']= fields['map'] 

        # fill out the CSV file
        row = [fields['name'],fields['url'], contact, fields['address'],fields['G_map'],
            fields['1bedroom'],fields['2bedroom']
               ,fields['3bedroom'],
               rent, fields['monthFees'], fields['onceFees'],
               fields['petPolicy'],
               fields['parking'], fields['gym'], fields['kitchen'],
               fields['amenities'], fields['features'], fields['space'],
               fields['lease'], fields['services'],
               fields['info'], fields['indoor'], fields['outdoor'],
               fields['description']]

        # add the score fields if necessary
        if pscores:
            for i in range(len(row), 0, -1):
                row.insert(i, '5')
            row.append('0')
        # write the row
        writer.writerow(row)

    # get the next page URL for pagination
    next_url = soup.find('a', class_='next')
    # if there's only one page this will actually be none
    if next_url is None:
        return

    # get the actual next URL address
    next_url = next_url.get('href')

    # recurse until the last page
    if next_url is not None and next_url != 'javascript:void(0)':
        write_parsed_to_csv(next_url, map_info, writer, pscores)


def parse_apartment_information(url, map_info):
    """For every apartment page, populate the required fields to be written to CSV"""

    # read the current page
    page = requests.get(url)

    # soupify the current page
    soup = BeautifulSoup(page.content, 'html.parser')
    soup.prettify()

    # the information we need to return as a dict
    fields = {}

    # get the name of the property
    get_property_name(soup, fields)

    # get the address of the property
    get_property_address(soup, fields)

    

    #get 1 bedroom info
    get_1bedroom(soup, fields)
     #get 2 bedroom info
    get_2bedroom(soup, fields)
     #get 3 bedroom info
    get_3bedroom(soup, fields)

    get_Score(soup, fields)
    get_ScoreStatus(soup, fields)
    get_Airport(soup, fields)
    get_Traffic(soup, fields)
    get_Businesses(soup, fields)
    get_Neighbourhood(soup, fields)
    get_Neighbourhood_overview(soup, fields)


    # get the link to open in maps
    fields['map'] = 'https://www.google.com/maps/dir/' \
                    + map_info['target_address'].replace(' ', '+') + '/' \
                    + fields['address'].replace(' ', '+') + '/data=!4m2!4m1!3e2'

    
    # get the one time and monthly fees
    get_fees(soup, fields)


    # get the description section
    get_description(soup, fields)

    # only look in this section (other sections are for example for printing)
    soup = soup.find('section', class_='specGroup js-specGroup')

    # get the pet policy of the property
    get_pet_policy(soup, fields)

    # get parking information
    get_parking_info(soup, fields)

    # get the amenities description
    get_field_based_on_class(soup, 'amenities', 'featuresIcon', fields)

    # get the 'interior information'
    get_field_based_on_class(soup, 'indoor', 'interiorIcon', fields)

    # get the 'outdoor information'
    get_field_based_on_class(soup, 'outdoor', 'parksIcon', fields)

    # get the 'gym information'
    get_field_based_on_class(soup, 'gym', 'fitnessIcon', fields)

    # get the 'kitchen information'
    get_field_based_on_class(soup, 'kitchen', 'kitchenIcon', fields)

    # get the 'services information'
    get_field_based_on_class(soup, 'services', 'servicesIcon', fields)

    # get the 'living space information'
    get_field_based_on_class(soup, 'space', 'sofaIcon', fields)

    # get the lease length
    get_field_based_on_class(soup, 'lease', 'leaseIcon', fields)

    # get the 'property information'
    get_features_and_info(soup, fields)


    return fields

def prettify_text(data):
    """Given a string, replace unicode chars and make it prettier"""

    # format it nicely: replace multiple spaces with just one
    data = re.sub(' +', ' ', data)
    # format it nicely: replace multiple new lines with just one
    data = re.sub('(\r?\n *)+', ',', data)
 
    # format it nicely: replace bullet with *
    data = re.sub(u'\u2022', ' ', data)
    # format it nicely: replace registered symbol with (R)
    data = re.sub(u'\xae', ' (R) ', data)
    # format it nicely: remove trailing spaces
    data = data.strip()
    # format it nicely: encode it, removing special symbols
    data = data.encode('utf8', 'ignore')

    return str(data,'utf-8')



def get_description(soup, fields):
    """Get the description for the apartment"""

    fields['description'] = ''

    if soup is None: return

    # find p with itemprop description
    obj = soup.find('p', {'itemprop': 'description'})

    if obj is not None:
        fields['description'] = prettify_text(obj.getText())


def get_1bedroom(soup, fields):
    """Given a beautifulSoup parsed page, extract the property size of the first one bedroom"""
    #note: this might be wrong if there are multiple matches!!!

    fields['1bedroom'] = ''

    if soup is None: return
    mylist=soup.find('tr', {'data-beds': '1'})
    if mylist is None: return
     # format it nicely: replace multiple spaces with just one
    mylist = re.sub(' +', '', mylist.text[100:400])
    # format it nicely: replace multiple new lines with just one
    mylist = re.sub('(\r?\n *)+', ':', mylist)
    
    fields['1bedroom'] =  mylist[:-1]

def get_2bedroom(soup, fields):
    """Given a beautifulSoup parsed page, extract the property size of the first one bedroom"""
    #note: this might be wrong if there are multiple matches!!!

    fields['2bedroom'] = ''

    if soup is None: return
    mylist2=soup.find('tr', {'data-beds': '2'})
    if mylist2 is None: return
 
     # format it nicely: replace multiple spaces with just one
    mylist2 = re.sub(' +', '', mylist2.text[100:400])
    # format it nicely: replace multiple new lines with just one
    mylist2 = re.sub('(\r?\n *)+', ':', mylist2)
    
    fields['2bedroom'] = (mylist2[:-1])

def get_3bedroom(soup, fields):
    """Given a beautifulSoup parsed page, extract the property size of the first one bedroom"""
    #note: this might be wrong if there are multiple matches!!!

    fields['3bedroom'] = ''

    if soup is None: return
    mylist3=soup.find('tr', {'data-beds': '3'})
    if mylist3 is None: return
     # format it nicely: replace multiple spaces with just one
    mylist3 = re.sub(' +', '', mylist3.text[100:400])
    # format it nicely: replace multiple new lines with just one
    mylist3 = re.sub('(\r?\n *)+', ':', mylist3)
    
    fields['3bedroom'] =(mylist3[:-1])
 

 


def get_features_and_info(soup, fields):
    """Given a beautifulSoup parsed page, extract the features and property information"""

    fields['features'] = ''
    fields['info'] = ''

    if soup is None: return
    
    obj = soup.find('i', class_='propertyIcon')

    if obj is not None:
        for obj in soup.find_all('i', class_='propertyIcon'):
            data = obj.parent.findNext('ul').getText()
            data = prettify_text(data)

            if obj.parent.findNext('h3').getText().strip() == 'Features':
                # format it nicely: remove trailing spaces
                fields['features'] = data[1:-1]
            if obj.parent.findNext('h3').getText() == 'Property Information':
                # format it nicely: remove trailing spaces
                
                fields['info'] = data[1:-1]


def get_field_based_on_class(soup, field, icon, fields):
    """Given a beautifulSoup parsed page, extract the specified field based on the icon"""

    fields[field] = ''

    if soup is None: return
    
    obj = soup.find('i', class_=icon)
    if obj is not None:
        data = obj.parent.findNext('ul').getText()
      

        fields[field] = prettify_text(data[1:-1])


def get_parking_info(soup, fields):
    """Given a beautifulSoup parsed page, extract the parking details"""

    fields['parking'] = ''

    if soup is None: return
    
    obj = soup.find('div', class_='parkingDetails')
    if obj is not None:
        data = obj.getText()
        data = prettify_text(data)

        # format it nicely: remove trailing spaces
        fields['parking'] = data[1:-1]


def get_pet_policy(soup, fields):
    """Given a beautifulSoup parsed page, extract the pet policy details"""
    if soup is None:
        fields['petPolicy'] = ''
        return
    
    # the pet policy
    data = soup.find('div', class_='petPolicyDetails')
    if data is None:
        data = ''
    else:
        data = data.getText()

    # format it nicely: remove the trailing whitespace
    fields['petPolicy'] = prettify_text(data[2:-2])


def get_fees(soup, fields):
    """Given a beautifulSoup parsed page, extract the one time and monthly fees"""

    fields['monthFees'] = ''
    fields['onceFees'] = ''

    if soup is None: return

    
    Onetime =soup.find('div', class_='oneTimeFees')
    RecurringCharges=soup.find('div', class_='monthlyFees')
    
    
        
    if Onetime is not None:
        fields['onceFees'] =   prettify_text(Onetime.text[1:-2])
    if RecurringCharges is not None:
        fields['monthFees'] =  prettify_text(RecurringCharges.text[1:-2])





def get_travel_time(map_url):
    """Get the travel distance & time from Google Maps distance matrix app given a URL"""

    # the travel info dict
    travel = {}

    # read and parse the google maps distance / duration from the api
    response = requests.get(map_url).json()
    
    # the status might not be OK, ignore this in that case
    if response['status'] == 'OK':
        response = response['rows'][0]['elements'][0]
        # extract the distance and duration
        if response['status'] == 'OK':
            # get the info
            travel['distance'] = response['distance']['text']
            travel['duration'] = response['duration']['text']

    # return the travel info
    return travel


def get_property_name(soup, fields):
    """Given a beautifulSoup parsed page, extract the name of the property"""
    fields['name'] = ''

    # get the name of the property
    obj = soup.find('h1', class_='propertyName')
    if obj is not None:
        name = obj.getText()
        name = prettify_text(name)
        fields['name'] = name[1:-1]


def get_property_address(soup, fields):
    """Given a beautifulSoup parsed page, extract the full address of the property"""

    # create the address from parts connected by comma (except zip code)
    address = []

    # this can be either inside the tags or as a value for "content"
    obj = soup.find(itemprop='streetAddress')
    text = obj.get('content')
    if text is None:
        text = obj.getText()
    text = prettify_text(text)
    address.append(text)

    obj = soup.find(itemprop='addressLocality')
    text = obj.get('content')
    if text is None:
        text = obj.getText()
    text = prettify_text(text)
    address.append(text)

    obj = soup.find(itemprop='addressRegion')
    text = obj.get('content')
    if text is None:
        text = obj.getText()
    text = prettify_text(text)
    address.append(text)

    # join the addresses on comma before getting the zip
    address = ', '.join(address)

    obj = soup.find(itemprop='postalCode')
    text = obj.get('content')
    if text is None:
        text = obj.getText()
    text = prettify_text(text)
    # put the zip with a space before it
    address += ' ' + text

    fields['address'] = address


def get_Score(soup, fields):
  
    fields['Score'] = ''

    if soup is None: return
    Score=soup.select(".soundScoreScore")[0].text 
    Score= prettify_text(Score)
    fields['Score'] = Score
 
def get_ScoreStatus(soup, fields):
    fields['ScoreStatus'] = ''

    if soup is None: return
    ScoreStatus=soup.select(".soundScoreStatus")[0].text
    ScoreStatus= prettify_text(ScoreStatus)
    fields['ScoreStatus'] = ScoreStatus

def get_Airport(soup, fields):
    fields['Airport'] = ''

    if soup is None: return
    Airport=soup.find('ul',"labels")(class_="ssAirportsData status")[0].text
    Airport= prettify_text(Airport)
    fields['Airport'] =Airport


def get_Traffic(soup, fields):
    fields['Traffic'] = ''

    if soup is None: return
    Traffic = soup.find('ul',"labels")(class_="ssTrafficData status")[0].text
    Traffic = prettify_text(Traffic )
    fields['Traffic '] = Traffic 


def get_Businesses(soup, fields):
    fields['Businesses'] = ''

    if soup is None: return
    Businesses=soup.select(".soundScoreScore")[0].text 
    Businesses= prettify_text(Businesses)
    fields['Businesses'] = Businesses


def get_Neighbourhood(soup, fields):
    fields['Neighbourhood'] = ''

    if soup is None: return
    Neighbourhood=soup.select(".soundScoreScore")[0].text 
    Neighbourhood= prettify_text(Neighbourhood)
    fields['Neighbourhood'] = Neighbourhood
def get_Neighbourhood_overview(soup, fields):
    fields['Neighbourhood_overview'] = ''

    if soup is None: return
    Neighbourhood_overview=soup.select(".soundScoreScore")[0].text 
    Neighbourhood_overview= prettify_text(Neighbourhood_overview)
    fields['Neighbourhood_overview'] = Neighbourhood_overview

def parse_config_times(given_time):
    """Convert the tomorrow at given_time New York time to seconds since epoch"""

    # tomorrow's date
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    # tomorrow's date/time string based on time given
    date_string = str(tomorrow) + ' ' + given_time
    # tomorrow's datetime object
    format_ = '%Y-%m-%d %I:%M %p'
    date_time = datetime.datetime.strptime(date_string, format_)

    # the epoch
    epoch = datetime.datetime.utcfromtimestamp(0)

    # return time since epoch in seconds, string without decimals
    time_since_epoch = (date_time - epoch).total_seconds()
    return str(int(time_since_epoch))


def main():
    """Read from the config file"""

    conf = configparser.ConfigParser()
    conf.read('address.ini')

    # get the apartments.com search URL
    apartments_url = conf.get('all', 'apartmentsURL')

    # get the name of the output file
    fname = conf.get('all', 'fname') + '.csv'

    # should this also print the scores
    pscores = (conf.get('all', 'printScores') in ['T', 't', '1', 'True', 'true'])

    # create a dict to pass in all of the Google Maps info to have fewer params
    map_info = {}

    # get the Google Maps information
    map_info['maps_url'] = conf.get('all', 'mapsURL')
    units = conf.get('all', 'mapsUnits')
    mode = conf.get('all', 'mapsMode')
    routing = conf.get('all', 'mapsTransitRouting')
    api_key = conf.get('all', 'mapsAPIKey')
    map_info['target_address'] = conf.get('all', 'targetAddress')

    # get the times for going to / coming back from work
    # and convert these to seconds since epoch, EST tomorrow
    map_info['morning'] = parse_config_times(conf.get('all', 'morning'))
    map_info['evening'] = parse_config_times(conf.get('all', 'evening'))

    # create the maps URL so we don't pass all the parameters
    map_info['maps_url'] += 'units=' + units + '&mode=' + mode + \
        '&transit_routing_preference=' + routing + '&key=' + api_key

    create_csv(apartments_url, map_info, fname, pscores)


if __name__ == '__main__':
    main()

