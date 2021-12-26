import sys, getopt, requests, urllib, csv, time
from fake_useragent import UserAgent
from xml.etree import ElementTree

def main(argv):
  state, city = parse_args(argv)

  region_id = '12447' # get_zillow_region_id(state, city)
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
  page = 1
  data = fetch_zillow_listings(region_id, page)
  total_result_count = data['cat1']['searchList']['totalResultCount']
  listings = data['cat1']['searchResults']['listResults']

  while total_result_count > 0:
    page += 1
    data = fetch_zillow_listings(region_id, page)
    listings += data['cat1']['searchResults']['listResults']
    total_result_count = data['cat1']['searchList']['totalResultCount']

  return list({v['zpid']:v for v in listings}.values())

def fetch_zillow_listings(region_id, page = 1):
  url = f"https://www.zillow.com/search/GetSearchPageState.htm?{build_search_query(region_id, page)}"
  print(url)
  response = requests.get(
    url,
    headers={
      'user-agent': 'Mozilla/5.0 (compatible; MSIE 5.0; Windows NT 5.2; Trident/5.1)',
      'accept': '*/*',
      'accept-encoding': 'gzip, deflate, br',
      'accept-language': 'en-US,en;q=0.9',
      'sec-fetch-mode': 'cors',
      'sec-fetch-dest': 'empty',
      'sec-gpc': '1',
      'sec-fetch-site': 'none'
    }
  )

  if (response.status_code != 200):
    print('failed to obtain listings from zillow:')
    print(response.content)
    sys.exit(2)

  return response.json()

def build_search_query(region_id, page):
  min = 500000
  max = 2000000

  # need to url encode a json string so it can be used as a query param
  # lat/lng is required and is hard coded to cover continental usa to allow any american city
  # price range hard coded to 500k-2m
  return urllib.parse.urlencode(
    {
      'searchQueryState': {
          "pagination": {"currentPage": page},
          "mapBounds": {
              "west": -124.848974,
              "east": -66.885444,
              "south": 24.396308,
              "north": 49.384358
          },
          "regionSelection": [{"regionId": region_id, "regionType": 6}],
          "isMapVisible": False,
          "filterState": {
              "beds": {"min": 2}, "baths":{"min": 2},
              "isMultiFamily": {"value":False}, "isApartmentOrCondo": {"value":False}, "isApartment": {"value":False}, "isCondo": {"value":False},
              "isLotLand": {"value": False}, "isManufactured": {"value":False},
              "price": {"min": min, "max": max}
              # "doz": {"value": "6m"}, "isForSaleByAgent": {"value": False},
              # "isForSaleByOwner": {"value": False}, "isNewConstruction": {"value": False},
              # "isForSaleForeclosure": {"value": False}, "isComingSoon": {"value": False},
              # "isAuction": {"value": False}, "isPreMarketForeclosure": {"value": False},
              # "isPreMarketPreForeclosure": {"value": False},
              # "isRecentlySold": {"value": True}, "isAllHomes": {"value": True},
              # "hasPool": {"value": True}, "hasAirConditioning": {"value": True},
              # "isApartmentOrCondo": {"value": False},
          },
          "isListVisible": True
      },
      'wants': {"cat1": ["listResults"], "cat2": ["total"]},
      'requestId': page
    }
  )
  # "{\"pagination\":{\"currentPage\":%i},\"mapBounds\":{\"west\":-124.848974,\"east\":-66.885444,\"south\":24.396308,\"north\":49.384358},\"regionSelection\":[{\"regionId\":%s,\"regionType\":6}],\"isMapVisible\":false,\"filterState\":{\"price\":{\"min\":50000,\"max\":200000}},\"isListVisible\":true}"%(page, region_id)

def write_listings_to_file(listings, state, city, region_id):
  # flatten the data so it can be stored as a csv
  flattened_listings = list(map(transform_listing, listings))
  filename = 'datasets/%s_%s_%s.csv'%(city, state, region_id)
  keys = flattened_listings[0].keys()
  with open(filename, 'w', newline='') as output_file:
    dict_writer = csv.DictWriter(output_file, keys)
    dict_writer.writeheader()
    dict_writer.writerows(flattened_listings)
  
  return filename

def transform_listing(listing):
  # additional_data = fetch_additional_data(listing)
  # print(additional_data)
  homeInfo = listing['hdpData']['homeInfo']
  return {
    'address': listing['address'],
    'zipcode': homeInfo.get('zipcode', None),
    'type': homeInfo.get('homeType', None),
    'status': homeInfo.get('homeStatus', None),
    'other_status': listing['statusText'],
    'price': homeInfo.get('price', None),
    # 'last_sold_price': additional_data.get('lastSoldPrice', None),
    # 'tax_assessed_value': additional_data.get('taxAssessedValue', None),
    # 'tax_assessed_year': additional_data.get('taxAssessedYear', None),
    # 'mortgage_rate': additional_data['mortgageRates'].get('thirtyYearFixedRate', None),
    # 'propert_tax_rate': additional_data.get('propertyTaxRate', None),
    'zestimate': homeInfo.get('zestimate', None),
    'festimate': homeInfo.get('festimate', None),
    'rent_zestimate': homeInfo.get('rentZestimate', None),
    'beds': listing['beds'],
    'baths': listing['baths'],
    'area': listing['area'],
    'year': homeInfo.get('yearBuilt', None),
    'price_reduction': homeInfo.get('priceReduction', None),
    'price_increase': homeInfo.get('priceChange', None),
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
    'mortgageRates': data.get('mortgageRates', { 'thirtyYearFixedRate': None }),
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