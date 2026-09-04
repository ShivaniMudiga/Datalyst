-- Kartly: an online fashion marketplace (Myntra/Meesho shaped) with its own
-- payments stack (Razorpay shaped). One database, because that is how a real
-- commerce company sees its business: catalogue, orders, money, logistics,
-- returns and acquisition spend side by side.

DROP TABLE IF EXISTS web_sessions, marketing_spend, product_reviews,
  returns, shipments, refunds, payments, order_items, orders,
  products, brands, sellers, customers CASCADE;

CREATE TABLE sellers (
  seller_id       serial PRIMARY KEY,
  seller_name     text NOT NULL,
  seller_city     text NOT NULL,
  seller_state    text NOT NULL,
  fulfilment_type text NOT NULL,          -- kartly_fulfilled | seller_shipped
  commission_pct  numeric(5,2) NOT NULL,
  seller_rating   numeric(3,2) NOT NULL,
  onboarded_on    date NOT NULL,
  is_active       boolean NOT NULL DEFAULT true
);

CREATE TABLE brands (
  brand_id         serial PRIMARY KEY,
  brand_name       text NOT NULL,
  is_private_label boolean NOT NULL DEFAULT false
);

CREATE TABLE products (
  product_id   serial PRIMARY KEY,
  sku          text NOT NULL UNIQUE,
  product_name text NOT NULL,
  brand_id     int NOT NULL REFERENCES brands(brand_id),
  seller_id    int NOT NULL REFERENCES sellers(seller_id),
  category     text NOT NULL,
  subcategory  text NOT NULL,
  mrp          numeric(10,2) NOT NULL,    -- listed price before discount
  cost_price   numeric(10,2) NOT NULL,    -- what Kartly pays the seller
  listed_on    date NOT NULL,
  is_active    boolean NOT NULL DEFAULT true
);

CREATE TABLE customers (
  customer_id         serial PRIMARY KEY,
  full_name           text NOT NULL,
  email               text NOT NULL UNIQUE,
  phone               text NOT NULL,
  city                text NOT NULL,
  state               text NOT NULL,
  city_tier           text NOT NULL,      -- tier_1 | tier_2 | tier_3
  signup_date         date NOT NULL,
  acquisition_channel text NOT NULL,      -- organic | google_ads | meta_ads | ...
  is_plus_member      boolean NOT NULL DEFAULT false
);

CREATE TABLE orders (
  order_id        serial PRIMARY KEY,
  customer_id     int NOT NULL REFERENCES customers(customer_id),
  placed_at       timestamptz NOT NULL,
  order_status    text NOT NULL,          -- delivered | shipped | cancelled | returned | pending
  channel         text NOT NULL,          -- android | ios | web | mobile_web
  payment_method  text NOT NULL,          -- upi | credit_card | debit_card | cod | ...
  is_cod          boolean NOT NULL,
  city            text NOT NULL,
  state           text NOT NULL,
  city_tier       text NOT NULL,
  coupon_code     text,
  items_total     numeric(10,2) NOT NULL, -- sum of line totals before discount
  discount_amount numeric(10,2) NOT NULL,
  shipping_fee    numeric(10,2) NOT NULL,
  order_total     numeric(10,2) NOT NULL  -- what the customer actually pays
);

CREATE TABLE order_items (
  order_item_id serial PRIMARY KEY,
  order_id      int NOT NULL REFERENCES orders(order_id),
  product_id    int NOT NULL REFERENCES products(product_id),
  seller_id     int NOT NULL REFERENCES sellers(seller_id),
  quantity      int NOT NULL,
  unit_price    numeric(10,2) NOT NULL,
  unit_cost     numeric(10,2) NOT NULL,
  discount      numeric(10,2) NOT NULL,
  line_total    numeric(10,2) NOT NULL,
  item_status   text NOT NULL
);

CREATE TABLE payments (
  payment_id      serial PRIMARY KEY,
  order_id        int NOT NULL REFERENCES orders(order_id),
  attempt_no      int NOT NULL,           -- 1 = first try; >1 means a retry
  gateway         text NOT NULL,          -- razorpay | payu | cashfree | cod_collection
  payment_method  text NOT NULL,
  bank_name       text,
  amount          numeric(10,2) NOT NULL,
  payment_status  text NOT NULL,          -- captured | failed | pending
  failure_reason  text,
  initiated_at    timestamptz NOT NULL,
  captured_at     timestamptz,
  gateway_fee     numeric(10,2) NOT NULL DEFAULT 0
);

CREATE TABLE refunds (
  refund_id     serial PRIMARY KEY,
  payment_id    int NOT NULL REFERENCES payments(payment_id),
  order_id      int NOT NULL REFERENCES orders(order_id),
  amount        numeric(10,2) NOT NULL,
  refund_reason text NOT NULL,
  refund_status text NOT NULL,            -- settled | processing | failed
  initiated_at  timestamptz NOT NULL,
  settled_at    timestamptz
);

CREATE TABLE shipments (
  shipment_id     serial PRIMARY KEY,
  order_id        int NOT NULL REFERENCES orders(order_id),
  courier         text NOT NULL,
  warehouse       text NOT NULL,
  shipped_at      timestamptz,
  promised_by     timestamptz NOT NULL,
  delivered_at    timestamptz,
  shipment_status text NOT NULL,          -- delivered | in_transit | rto | cancelled
  is_rto          boolean NOT NULL DEFAULT false,
  shipping_cost   numeric(10,2) NOT NULL
);

CREATE TABLE returns (
  return_id     serial PRIMARY KEY,
  order_id      int NOT NULL REFERENCES orders(order_id),
  order_item_id int NOT NULL REFERENCES order_items(order_item_id),
  return_reason text NOT NULL,            -- size_issue | quality | wrong_item | ...
  return_status text NOT NULL,
  refund_amount numeric(10,2) NOT NULL,
  initiated_at  timestamptz NOT NULL,
  resolved_at   timestamptz
);

CREATE TABLE product_reviews (
  review_id   serial PRIMARY KEY,
  product_id  int NOT NULL REFERENCES products(product_id),
  customer_id int NOT NULL REFERENCES customers(customer_id),
  order_id    int NOT NULL REFERENCES orders(order_id),
  rating      int NOT NULL,
  review_text text,
  created_at  timestamptz NOT NULL
);

CREATE TABLE marketing_spend (
  spend_id     serial PRIMARY KEY,
  spend_date   date NOT NULL,
  channel      text NOT NULL,             -- google_ads | meta_ads | influencer | ...
  campaign     text NOT NULL,
  impressions  bigint NOT NULL,
  clicks       int NOT NULL,
  spend_amount numeric(12,2) NOT NULL
);

CREATE TABLE web_sessions (
  session_id     bigserial PRIMARY KEY,
  customer_id    int REFERENCES customers(customer_id),
  started_at     timestamptz NOT NULL,
  device         text NOT NULL,
  channel        text NOT NULL,
  landing_page   text NOT NULL,
  pages_viewed   int NOT NULL,
  added_to_cart  boolean NOT NULL,
  converted      boolean NOT NULL,
  session_secs   int NOT NULL
);

CREATE INDEX ON orders (placed_at);
CREATE INDEX ON orders (customer_id);
CREATE INDEX ON orders (order_status);
CREATE INDEX ON order_items (order_id);
CREATE INDEX ON order_items (product_id);
CREATE INDEX ON payments (order_id);
CREATE INDEX ON payments (payment_status);
CREATE INDEX ON payments (initiated_at);
CREATE INDEX ON shipments (order_id);
CREATE INDEX ON returns (order_id);
CREATE INDEX ON products (category, subcategory);
CREATE INDEX ON web_sessions (started_at);
CREATE INDEX ON marketing_spend (spend_date);
