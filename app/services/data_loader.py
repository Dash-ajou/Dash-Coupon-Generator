import pymysql
from app.models.schema import DataBundle, Request, Partner, Issue, Coupon, Product
from app.config.db_config import DB_CONFIG

def load_data_by_request_id(request_id: int) -> DataBundle:
    # Connect to the database
    conn = pymysql.connect(**DB_CONFIG)
    try:
        try:
            with conn.cursor() as cursor:
                # 1. Fetch request and partner info
                cursor.execute("""
                    SELECT r.request_id, r.coupon_form, pu.partner_id, pu.partner_name
                    FROM request r
                    JOIN partner_user pu ON r.partner_id = pu.partner_id
                    WHERE r.request_id = %s
                """, (request_id,))
                req_row = cursor.fetchone()
                partner = Partner(partner_id=req_row['partner_id'], partner_name=req_row['partner_name'])
                request = Request(request_id=req_row['request_id'], coupon_form=req_row['coupon_form'], partner=partner)

                print(partner)
                print(request)

                # 2. Fetch issue
                cursor.execute("SELECT issue_id FROM issue WHERE request_id = %s", (request_id,))
                issues = cursor.fetchall()
                issue_id = issues[0]['issue_id'] if issues else None

                # 3. Fetch coupons
                cursor.execute("SELECT coupon_id, registration_code, product_id FROM coupon WHERE issue_id = %s", (issue_id,))
                coupon_rows = cursor.fetchall()

                # 4. Fetch products (distinct)
                product_ids = list({row['product_id'] for row in coupon_rows})
                format_strings = ','.join(['%s'] * len(product_ids))
                cursor.execute(f"SELECT product_id, product_name FROM product WHERE product_id IN ({format_strings})", tuple(product_ids))
                product_map = {row['product_id']: Product(**row) for row in cursor.fetchall()}

                # 5. Build coupons
                coupons = []
                for row in coupon_rows:
                    product_id_on_coupon = row['product_id']
                    product = product_map.get(product_id_on_coupon)
                    if not product:
                        print(f"[WARNING] No product found for product_id: {row['product_id']}")
                        continue
                    coupons.append(
                        Coupon(
                            coupon_id=row['coupon_id'],
                            registration_code=row['registration_code'],
                            product=product
                        )
                    )

                issue = Issue(issue_id=issue_id, coupons=coupons)
                return DataBundle(request=request, issue=issue)
        except Exception as e:
            print(f"[ERROR] Failed to load data for request_id={request_id}: {e}")
            raise

    finally:
        conn.close()