import asyncio
import aiohttp
import requests
from logger.logger import init_logger
from entitity.product import Product


log = init_logger(__name__)


class WBParser:

    sign: str= "WB"

    list_products: list[Product] = []
    list_json_pages: list[dict] = []

    base_wb_url: str = "https://catalog.wb.ru/"
    page: int = 1

    num_products_on_page: int = 99

    def build_wb_api_url(self) -> str:

        if self.page == 1:
            api_url: str = (f"{self.base_wb_url}catalog/new_year4/v2/"
                            f"catalog?ab_testing=false&appType=1&cat=130404&curr=rub&dest=-5818883&sort=popular&spp=30")
            return api_url
        else:
            api_url: str = (f"{self.base_wb_url}catalog/new_year4/v2/"
                            f"catalog?ab_testing=false&appType=1&cat=130404&curr=rub&dest=-5818883&page={self.page}&sort=popular&spp=30")
            return api_url

    def make_request(self) -> requests.Response | None:

        url: str = self.build_wb_api_url()

        response = requests.get(url)
        if response.status_code != 200:
            return
        else:
            return response

    def get_page_numbers(self) -> int | None:

        response = self.make_request()

        data: dict = response.json().get("data")

        if data is None:
            return

        num_products: int = data.get("total")
        if num_products is None:
            return

        return int(num_products // self.num_products_on_page)

    def build_urls(self) -> list[str]:

        all_pages = self.get_page_numbers()
        log.info(f"{self.sign} All pages to parse: {all_pages}")

        list_urls: list[str] = []

        for _ in range(1, 4):

            api_url = self.build_wb_api_url()
            list_urls.append(api_url)
            self.page += 1

        return list_urls

    @staticmethod
    def get_products(data_products: dict) -> list[dict] | None:

        data = data_products.get("data")

        if not data:
            return

        products = data.get("products")
        if not products:
            return

        return products

    def create_product_object(self, product_wb: dict) -> Product:

        new_product = Product(
            name=product_wb.get("name"),
            full_price=product_wb.get("sizes")[0].get("price").get("basic") // 100,
            price_with_discount=product_wb.get("sizes")[0].get("price").get("product") // 100,
            url=f"https://www.wildberries.ru/catalog/{product_wb.get('id')}/detail.aspx",
            in_stock=product_wb.get("totalQuantity")
        )

        log.debug(f"{self.sign} New product {product_wb.get("name")} added")
        return new_product

    def parse_products(self) -> None:

        for json_page in self.list_json_pages:

            products = self.get_products(json_page)
            if products is None:
                continue

            for pr in products:
                new_product = self.create_product_object(pr)
                self.list_products.append(new_product)

    async def get_product_data(self, sess: aiohttp.ClientSession, url: str):
        async with sess.get(url=url) as response:

            if response.status != 200:
                return

            data: dict = await response.json()

            self.list_json_pages.append(data)

    async def parse_wb(self) -> None:

        list_urls = await asyncio.to_thread(self.build_urls)
        log.info(f"{self.sign} Number urls with products to parse {len(list_urls)}")

        async with aiohttp.ClientSession() as sess:
            tasks: list = []
            for url in list_urls:
                task = asyncio.create_task(self.get_product_data(sess, url))
                tasks.append(task)

            await asyncio.gather(*tasks)

        await asyncio.to_thread(self.parse_products)

        log.info(f"{self.sign} New products to add {len(self.list_products)}")
        # print(self.list_products)


