from csv_price_processor.aws.transformer import csv_to_pricebooks

def test_unit():
    assert True

def load_csv_file_to_pricebooks():
    with open(f'data/test_price_data_csv.csv') as csvfile:
        price_books = csv_to_pricebooks(csvfile)
        return price_books

def test_transformer_response():
    mock_pricebooks = load_csv_file_to_pricebooks()
    no_of_items = len(mock_pricebooks['items'])
    pricebook_value = mock_pricebooks['head']['pricebook']
    catalog_value = mock_pricebooks['head']['catalog']
    currency_value = mock_pricebooks['head']['currency']

    assert no_of_items > 0

    assert pricebook_value == 'default'

    assert catalog_value == 'storefront-catalog-en'

    assert currency_value == 'USD'
