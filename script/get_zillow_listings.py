import sys, getopt, requests, urllib, csv, time
from fake_useragent import UserAgent
from xml.etree import ElementTree

def main(argv):
  state, city = parse_args(argv)

  region_id = get_zillow_region_id(state, city)
  print('zillow region id: ' + region_id)

  listings = get_zillow_listings_for_region(region_id)
  print('zillow listings in region found: ' + str(len(listings)))

  filename = write_listings_to_file(listings, state, city, region_id)
  print('output file: ' + filename)

def get_zillow_region_id(state, city):
  response = requests.get(
    'https://www.zillow.com/webservice/GetRegionChildren.htm',
    params={
      'zws-id': 'X1-ZWz1hkkltuo8wb_8tgid',
      'city': city,
      'state': state
    }
  )

  # it's fucking xml?!
  return ElementTree.fromstring(response.content).find('response').find('region').find('id').text

def get_zillow_listings_for_region(region_id):
  data = fetch_zillow_listings(region_id)
  total_pages = data['searchList']['totalPages']
  listings = data['searchResults']['listResults']

  for page in range(2, total_pages + 1):
    data = fetch_zillow_listings(region_id, page)
    listings += data['searchResults']['listResults']

  return list({v['zpid']:v for v in listings}.values())

def fetch_zillow_listings(region_id, page = 1):
  response = requests.get(
    'https://www.zillow.com/search/GetSearchPageState.htm',
    params={
      'searchQueryState': build_search_query(region_id, page),
      'includeMap': 'false',
      'includeList': 'true'
    },
    headers={
      'user-agent': 'Mozilla/5.0 (Windows NT 6.2; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/32.0.1667.0 Safari/537.36',
      'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3',
      'accept-encoding': 'gzip, deflate, br',
      'accept-language': 'en-US,en;q=0.9',
      'sec-fetch-mode': 'navigate',
      'sec-fetch-site': 'none',
      'upgrade-insecure-requests': '1'
    }
  )

  if (response.status_code != 200):
    print('failed to obtain listings from zillow:')
    print(response.content)
    sys.exit(2)

  return response.json()

def build_search_query(region_id, page):
  # need to url encode a json string so it can be used as a query param
  # lat/lng is required and is hard coded to cover continental usa to allow any american city
  # price range hard coded to 50k-200k
  return urllib.parse.quote(
    "{\"pagination\":{\"currentPage\":%i},\"mapBounds\":{\"west\":-124.848974,\"east\":-66.885444,\"south\":24.396308,\"north\":49.384358},\"regionSelection\":[{\"regionId\":%s,\"regionType\":6}],\"isMapVisible\":false,\"filterState\":{\"price\":{\"min\":50000,\"max\":200000}},\"isListVisible\":true}"%(page, region_id)
  )

def write_listings_to_file(listings, state, city, region_id):
  # flatten the data so it can be stored as a csv
  flattened_listings = list(map(transform_listing, listings))
  filename = '%s_%s_%s.csv'%(city, state, region_id)
  keys = flattened_listings[0].keys()
  with open(filename, 'w', newline='') as output_file:
    dict_writer = csv.DictWriter(output_file, keys)
    dict_writer.writeheader()
    dict_writer.writerows(flattened_listings)
  
  return filename

def transform_listing(listing):
  additional_data = fetch_additional_data(listing)
  homeInfo = listing['hdpData']['homeInfo']
  return {
    'address': listing['address'],
    'zipcode': homeInfo.get('zipcode', None),
    'type': homeInfo.get('homeType', None),
    'status': homeInfo.get('homeStatus', None),
    'other_status': listing['statusText'],
    'price': homeInfo.get('price', None),
    'last_sold_price': additional_data.get('lastSoldPrice', None),
    'zestimate': homeInfo.get('zestimate', None),
    'festimate': homeInfo.get('festimate', None),
    'rent_zestimate': homeInfo.get('rentZestimate', None),
    'beds': listing['beds'],
    'baths': listing['baths'],
    'area': listing['area'],
    'year': homeInfo.get('yearBuilt', None),
    'reduction': homeInfo.get('priceReduction', None),
    'tax_assessed_value': additional_data.get('taxAssessedValue', None),
    'tax_assessed_year': additional_data.get('taxAssessedYear', None),
    'mortgage_rate': additional_data.get('thirtyYearFixedRate', None),
    'propert_tax_rate': additional_data.get('propertyTaxRate', None),
    'days_on_zillow': homeInfo.get('daysOnZillow', None),
    'extra_info': listing['variableData']['text'],
    'extra_info_type': listing['variableData']['type'],
    'zpid': listing['zpid'],
    'id': listing['id'],
    'link': listing['detailUrl']
  }

def fetch_additional_data(listing):
  response = requests.post(
    'https://www.zillow.com/graphql/',
    params={
      'zpid': listing['zpid'],
      'queryId': '4f7d72d05b119ce8d8cc87dc6f5c6cc2',
      'operationName': 'ForSaleDoubleScrollFullRenderQuery'
    },
    headers={
      'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.108 Safari/537.36',
      'origin': 'https://www.zillow.com',
      'referer': listing['detailUrl'],
      'sec-fetch-mode': 'cors',
      'sec-fetch-site': 'same-origin',
      'accept': '*/*',
      'accept-encoding': 'gzip, deflate, br',
      'accept-language': 'en-US,en;q=0.9'
    },
    json={
      "operationName": "ForSaleDoubleScrollFullRenderQuery",
      "variables": {
        "zpid": listing['zpid'],
        "contactFormRenderParameter": {
          "zpid":listing['zpid'],
          "platform": "desktop",
          "isDoubleScroll": 'true'
        }
      },
      "clientVersion": "home-details/5.49.24.2.master.ee287a1",
      "queryId":"4f7d72d05b119ce8d8cc87dc6f5c6cc2"
    }
  )

  print(response.url)
  if (response.status_code != 200):
    print('failed to obtain additional data for ' + listing['zpid'] + ':')
    print(response.content)
    return {}

  data = response.json()['data']['property']
  time.sleep(1)

  return {
    'lastSoldPrice': data['lastSoldPrice'],
    'taxAssessedValue': data['taxAssessedValue'],
    'taxAssessedYear': data['taxAssessedYear'],
    'thirtyYearFixedRate': data['mortgageRates']['thirtyYearFixedRate'],
    'propertyTaxRate': data['propertyTaxRate'],
  }

def parse_args(argv):
  try:
    opts, args = getopt.getopt(argv,'hs:c:',['state=','city='])
  except getopt.GetoptError:
    print('get_zillow_listings.py -s <state> -c <city>')
    sys.exit(2)
  for opt, arg in opts:
    if opt == '-h':
      print('get_zillow_listings.py -s <state> -c <city>')
      sys.exit()
    elif opt in ('-s', '--state'):
      state = arg
    elif opt in ('-c', '--city'):
      city = arg

  try:
    state, city
  except NameError:
    print('both state and city are required')
    print('get_zillow_listings.py -s <state> -c <city>')
    sys.exit(2)
  return state, city

if __name__ == '__main__':
  main(sys.argv[1:])