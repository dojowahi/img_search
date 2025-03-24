import requests
from app.core.config import settings


class TargetProductAPI:
    def __init__(self):
        self.headers = {
            "X-RapidAPI-Key": settings.SHOPPING_API_KEY,
            "X-RapidAPI-Host": "target-com-shopping-api.p.rapidapi.com"
        }

    def _get_json(self, url, params):
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API Error: {e}")
            return None

    def search_products(self, keyword="shoes", count="2",store_id="862"):
        url = "https://target-com-shopping-api.p.rapidapi.com/product_search"
        params = {"store_id": store_id, "keyword": keyword, "count": count, "offset": "0"}
        return self._get_json(url, params)

    def get_product_details(self, tcin,store_id="862"):
        url = "https://target-com-shopping-api.p.rapidapi.com/product_details"
        params = {"store_id": store_id, "tcin": tcin}
        return self._get_json(url, params)

    def extract_product_info(self, product):
        try:
            return {
                "tcin": product["tcin"],
                "image_url": product["item"]["enrichment"]["images"]["primary_image_url"],
                "price": product["price"]["formatted_current_price"],
                "title": product["item"]["product_description"]["title"],
            }
        except (KeyError, TypeError):
            return None

    def extract_product_details(self, product_data):
        try:
            product = product_data['data']['product']
            return {
                'reviews': product['ratings_and_reviews'],
                'product_details': product['item']
            }
        except (KeyError, TypeError):
            return None


target_service = TargetProductAPI()
# def target_product_search_simplified(api_key, keyword="shoes", count="2"):
#     api = TargetProductAPI(api_key)
#     results = api.search_products(keyword, count)
#     if results and 'data' in results and 'search' in results['data'] and 'products' in results['data']['search']:
#         return [api.extract_product_info(p) for p in results['data']['search']['products'] if api.extract_product_info(p)]
#     return None

# def target_product_details_simplified(api_key, tcin):
#     api = TargetProductAPI(api_key)
#     details = api.get_product_details(tcin)
#     if details:
#         return api.extract_product_details(details)
#     return None

# Example usage:
# api_key = "YOUR_API_KEY"
# search_results = target_product_search_simplified(api_key, keyword="shoes", count="3")
# if search_results:
#     print(search_results)
#     if search_results:
#         tcin_to_detail = search_results[0]['tcin']
#         product_details = target_product_details_simplified(api_key, tcin_to_detail)
#         print(product_details)