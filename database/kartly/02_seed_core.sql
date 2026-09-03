-- Reference data, customers, orders and order lines.
-- Deterministic: setseed makes every rerun produce the same marketplace.
SELECT setseed(0.4242);

TRUNCATE customers, sellers, brands, products, orders, order_items,
         payments, refunds, shipments, returns, product_reviews,
         marketing_spend, web_sessions RESTART IDENTITY CASCADE;

-- Per-row pseudo-random in [0,1). random() inside an uncorrelated LATERAL is
-- hoisted and evaluated once for the whole statement; a hash of the row key
-- is not, and it makes the seed reproducible.
CREATE OR REPLACE FUNCTION rnd(seed text) RETURNS numeric LANGUAGE sql IMMUTABLE AS
$$ SELECT abs(mod(hashtextextended(seed, 42), 1000000000))::numeric / 1000000000 $$;

-- Geography, repeated by weight so metro traffic dominates the way it really does.
CREATE TEMP TABLE geo AS
SELECT row_number() OVER () AS idx, city, state, tier
FROM (VALUES
  ('Mumbai','Maharashtra','tier_1',10), ('Bengaluru','Karnataka','tier_1',10),
  ('Delhi','Delhi','tier_1',9),         ('Hyderabad','Telangana','tier_1',8),
  ('Pune','Maharashtra','tier_1',7),    ('Chennai','Tamil Nadu','tier_1',7),
  ('Kolkata','West Bengal','tier_1',6), ('Ahmedabad','Gujarat','tier_1',5),
  ('Jaipur','Rajasthan','tier_2',5),    ('Lucknow','Uttar Pradesh','tier_2',4),
  ('Indore','Madhya Pradesh','tier_2',4),('Nagpur','Maharashtra','tier_2',3),
  ('Coimbatore','Tamil Nadu','tier_2',3),('Kochi','Kerala','tier_2',3),
  ('Chandigarh','Chandigarh','tier_2',3),('Surat','Gujarat','tier_2',3),
  ('Bhopal','Madhya Pradesh','tier_2',2),('Visakhapatnam','Andhra Pradesh','tier_2',2),
  ('Guwahati','Assam','tier_3',2),      ('Ranchi','Jharkhand','tier_3',2),
  ('Raipur','Chhattisgarh','tier_3',2), ('Jodhpur','Rajasthan','tier_3',2),
  ('Mysuru','Karnataka','tier_3',2),    ('Siliguri','West Bengal','tier_3',1),
  ('Bareilly','Uttar Pradesh','tier_3',1),('Warangal','Telangana','tier_3',1),
  ('Hubli','Karnataka','tier_3',1),     ('Tirupati','Andhra Pradesh','tier_3',1)
) AS v(city,state,tier,w), LATERAL generate_series(1, v.w);

CREATE TEMP TABLE cat AS
SELECT row_number() OVER () AS idx, category, subcategory, low, high, return_bias
FROM (VALUES
  ('Women Western Wear','Dresses',       799, 4999, 1.45),
  ('Women Western Wear','Tops',          399, 2499, 1.40),
  ('Women Western Wear','Jeans',         999, 3999, 1.50),
  ('Women Ethnic Wear','Kurtas',         599, 3499, 1.30),
  ('Women Ethnic Wear','Sarees',        1199, 9999, 1.20),
  ('Women Ethnic Wear','Lehengas',      2999,24999, 1.35),
  ('Men Topwear','T-Shirts',             349, 1999, 1.05),
  ('Men Topwear','Shirts',               699, 3499, 1.15),
  ('Men Topwear','Jackets',             1499, 8999, 1.10),
  ('Men Bottomwear','Jeans',             899, 4499, 1.35),
  ('Men Bottomwear','Trousers',          799, 3999, 1.20),
  ('Men Bottomwear','Shorts',            499, 1999, 1.00),
  ('Footwear','Sneakers',               1299, 9999, 1.25),
  ('Footwear','Sandals',                 599, 2999, 1.10),
  ('Footwear','Formal Shoes',           1499, 7999, 1.20),
  ('Beauty & Grooming','Skincare',       249, 2999, 0.35),
  ('Beauty & Grooming','Makeup',         299, 3499, 0.40),
  ('Beauty & Grooming','Fragrance',      699, 5999, 0.30),
  ('Accessories','Watches',              999,14999, 0.65),
  ('Accessories','Bags',                 799, 6999, 0.70),
  ('Accessories','Sunglasses',           599, 4999, 0.75),
  ('Home & Living','Bedsheets',          699, 3999, 0.45),
  ('Home & Living','Decor',              399, 4999, 0.50),
  ('Home & Living','Kitchen',            299, 5999, 0.40)
) AS v(category, subcategory, low, high, return_bias);

INSERT INTO sellers (seller_name, seller_city, seller_state, fulfilment_type, commission_pct, seller_rating, onboarded_on, is_active)
SELECT
  (ARRAY['Vastra','Trendline','Nexa Retail','Urban Loom','Silk Route','Fabrica','Shreeji','Metro Styles',
         'Coastal Threads','Ridge Apparel','Kalpana Exports','Bloom & Co','Zenith Traders','Anaya Retail',
         'Pinnacle Lifestyle','Weave House','Craftly','Northstar Goods'])[1 + (s % 18)]
    || ' ' || (ARRAY['Pvt Ltd','LLP','Enterprises','Trading Co','Retail'])[1 + (s % 5)],
  g.city, g.state,
  CASE WHEN random() < 0.62 THEN 'kartly_fulfilled' ELSE 'seller_shipped' END,
  round((8 + random()*14)::numeric, 2),
  round((3.1 + random()*1.85)::numeric, 2),
  DATE '2023-01-01' + (random()*900)::int,
  random() > 0.06
FROM (SELECT s, (1 + floor(random()*(SELECT max(idx) FROM geo)))::int AS gi FROM generate_series(1,90) s) x
JOIN geo g ON g.idx = x.gi;

INSERT INTO brands (brand_name, is_private_label)
SELECT b.name, b.name LIKE 'Kartly%'
FROM (VALUES
  ('Kartly Basics'),('Kartly Luxe'),('Kartly Home'),('Auralia'),('Meraki'),('Nova Threads'),
  ('Denimworks'),('Sable & Stone'),('Indigo Lane'),('Tashan'),('Rangrez'),('Mystiq'),
  ('Zaria'),('Kaya Naturals'),('Bloomvale'),('Urbanik'),('Peak Trail'),('Solstice'),
  ('Verve & Co'),('Lumen'),('Attic Wear'),('Rivera'),('Nimbus'),('Kaftan Club'),
  ('Studio Nine'),('Terra Home'),('Pashmi'),('Orbit Athletics'),('Velvette'),('Chai Street'),
  ('Aurum'),('Grovehouse'),('Noor Beauty'),('Steelcraft'),('Marigold')
) AS b(name);

INSERT INTO products (sku, product_name, brand_id, seller_id, category, subcategory, mrp, cost_price, listed_on, is_active)
SELECT
  'KRT-' || lpad(p::text, 6, '0'),
  b.brand_name || ' ' ||
    (ARRAY['Relaxed','Slim Fit','Printed','Solid','Embroidered','Oversized','Classic','Textured',
           'Handloom','Everyday','Premium','Colourblock'])[1 + (p % 12)]
    || ' ' || c.subcategory,
  b.brand_id, s.seller_id, c.category, c.subcategory,
  mrp, round((mrp * (0.40 + random()*0.28))::numeric, 2),
  DATE '2023-06-01' + (random()*1080)::int,
  random() > 0.11
FROM (
  SELECT p,
    (1 + floor(random()*35))::int AS bi,
    (1 + floor(random()*90))::int AS si,
    (1 + floor(random()*24))::int AS ci,
    random() AS r
  FROM generate_series(1,1800) p
) x
JOIN brands b ON b.brand_id = x.bi
JOIN sellers s ON s.seller_id = x.si
JOIN cat c ON c.idx = x.ci
CROSS JOIN LATERAL (SELECT round((c.low + power(x.r, 1.9) * (c.high - c.low))::numeric, 0) AS mrp) m;

-- Customers are inserted in signup order, so customer_id ascending == signup
-- ascending. Orders below rely on that to never predate a signup.
INSERT INTO customers (full_name, email, phone, city, state, city_tier, signup_date, acquisition_channel, is_plus_member)
SELECT
  (ARRAY['Aarav','Vivaan','Aditya','Vihaan','Arjun','Sai','Reyansh','Krishna','Ishaan','Rohan',
         'Ananya','Diya','Aadhya','Saanvi','Myra','Anika','Navya','Kiara','Riya','Ira',
         'Kabir','Neel','Rahul','Priya','Meera','Nikhil','Tanvi','Zoya','Faisal','Karthik',
         'Lakshmi','Deepak','Sneha','Varun','Pooja','Imran','Anjali','Rithik','Shreya','Manav'])[1 + (c % 40)]
  || ' ' ||
  (ARRAY['Sharma','Verma','Patel','Reddy','Nair','Iyer','Singh','Gupta','Mehta','Joshi',
         'Rao','Das','Bose','Kulkarni','Desai','Malhotra','Chopra','Kapoor','Banerjee','Menon',
         'Pillai','Shetty','Ahuja','Khan','Sheikh','Bhat','Naidu','Mishra','Tiwari','Chatterjee'])[1 + ((c*7) % 30)],
  'user' || c || '@' || (ARRAY['gmail.com','outlook.com','yahoo.in','proton.me'])[1 + (c % 4)],
  '9' || lpad(((c * 8237) % 1000000000)::text, 9, '0'),
  g.city, g.state, g.tier,
  DATE '2024-06-01' + floor(810 * power(c::numeric / 26000, 0.6))::int,
  CASE WHEN r2 < 0.30 THEN 'organic' WHEN r2 < 0.52 THEN 'google_ads'
       WHEN r2 < 0.72 THEN 'meta_ads' WHEN r2 < 0.83 THEN 'influencer'
       WHEN r2 < 0.92 THEN 'referral' ELSE 'email' END,
  r3 < 0.14
FROM (
  SELECT c, (1 + floor(random()*(SELECT max(idx) FROM geo)))::int AS gi,
         random() AS r2, random() AS r3
  FROM generate_series(1,26000) c
) x
JOIN geo g ON g.idx = x.gi
ORDER BY c;

-- Daily order volume: a growing business with festive spikes (October),
-- end-of-season sales (January, July) and a weekend uplift.
CREATE TEMP TABLE day_volume AS
SELECT d::date AS day,
  GREATEST(6, round(
      (38 + 92.0 * (d::date - DATE '2024-09-01') / 729.0)
    * CASE extract(month FROM d)
        WHEN 10 THEN 2.15 WHEN 11 THEN 1.32 WHEN 12 THEN 1.14
        WHEN 1  THEN 1.52 WHEN 7  THEN 1.44 WHEN 2 THEN 0.90
        WHEN 3  THEN 0.94 WHEN 4  THEN 1.00 WHEN 5 THEN 1.06
        WHEN 6  THEN 0.93 WHEN 8  THEN 1.02 ELSE 1.00 END
    * CASE WHEN extract(isodow FROM d) >= 6 THEN 1.24 ELSE 1.00 END
    * (0.90 + random()*0.20)
  ))::int AS order_count
FROM generate_series(DATE '2024-09-01', DATE '2026-08-30', INTERVAL '1 day') d;

INSERT INTO orders (customer_id, placed_at, order_status, channel, payment_method, is_cod,
                    city, state, city_tier, coupon_code, items_total, discount_amount, shipping_fee, order_total)
SELECT
  cu.customer_id,
  x.day + make_interval(hours => x.hour, mins => (random()*59)::int),
  'pending',                                    -- corrected once payments and shipments exist
  CASE WHEN x.rch < 0.52 THEN 'android' WHEN x.rch < 0.74 THEN 'ios'
       WHEN x.rch < 0.90 THEN 'mobile_web' ELSE 'web' END,
  CASE WHEN x.rpm < cod_p THEN 'cod'
       WHEN x.rpm < cod_p + 0.42 THEN 'upi'
       WHEN x.rpm < cod_p + 0.55 THEN 'credit_card'
       WHEN x.rpm < cod_p + 0.64 THEN 'debit_card'
       WHEN x.rpm < cod_p + 0.71 THEN 'netbanking'
       WHEN x.rpm < cod_p + 0.77 THEN 'wallet'
       ELSE 'emi' END,
  x.rpm < cod_p,
  cu.city, cu.state, cu.city_tier,
  CASE WHEN x.rcp < 0.34 THEN (ARRAY['FLAT10','WELCOME15','KARTLY20','EOSS25','APPONLY5'])[1 + (x.n % 5)] END,
  0, 0, 0, 0
FROM (
  SELECT dv.day, n,
    -- eligible = customers who had signed up by this day (see signup formula)
    GREATEST(400, LEAST(26000, floor(26000 * power(
        GREATEST(1, dv.day - DATE '2024-06-01')::numeric / 810, 1.0/0.6))))::int AS eligible,
    (ARRAY[9,10,11,12,13,14,15,16,17,18,19,20,20,21,21,21,22,22,23,8])[1 + floor(random()*20)::int] AS hour,
    random() AS rcu, random() AS rch, random() AS rpm, random() AS rcp
  FROM day_volume dv, generate_series(1, dv.order_count) n
) x
JOIN customers cu ON cu.customer_id = 1 + floor(power(x.rcu, 1.45) * x.eligible)::int
CROSS JOIN LATERAL (SELECT CASE cu.city_tier WHEN 'tier_1' THEN 0.15 WHEN 'tier_2' THEN 0.26 ELSE 0.38 END AS cod_p) t;

INSERT INTO order_items (order_id, product_id, seller_id, quantity, unit_price, unit_cost, discount, line_total, item_status)
SELECT
  o.order_id, p.product_id, p.seller_id, q.qty,
  pr.price, p.cost_price,
  round((p.mrp - pr.price) * q.qty, 2),
  round(pr.price * q.qty, 2),
  'ordered'
FROM orders o
CROSS JOIN LATERAL generate_series(1,
  CASE WHEN rnd(o.order_id || ':n') < 0.56 THEN 1
       WHEN rnd(o.order_id || ':n') < 0.83 THEN 2
       WHEN rnd(o.order_id || ':n') < 0.95 THEN 3 ELSE 4 END) AS i
CROSS JOIN LATERAL (
  SELECT (1 + floor(power(rnd(o.order_id || ':p:' || i), 1.7) * 1800))::int AS pi,
         rnd(o.order_id || ':d:' || i) AS rd,
         CASE WHEN rnd(o.order_id || ':q:' || i) < 0.86 THEN 1
              WHEN rnd(o.order_id || ':q:' || i) < 0.97 THEN 2 ELSE 3 END AS qty
) q
JOIN products p ON p.product_id = q.pi
CROSS JOIN LATERAL (
  SELECT round((p.mrp * (1 - LEAST(0.72,
      CASE WHEN extract(month FROM o.placed_at) IN (1,7,10) THEN 0.28 ELSE 0.12 END
      + q.rd * 0.42)))::numeric, 2) AS price
) pr;

UPDATE orders o
SET items_total     = t.items_total,
    discount_amount = round(t.item_discount + c.coupon, 2),
    shipping_fee    = c.ship,
    order_total     = round(t.items_total - c.coupon + c.ship, 2)
FROM (
  SELECT order_id, sum(line_total) AS items_total, sum(discount) AS item_discount
  FROM order_items GROUP BY order_id
) t
CROSS JOIN LATERAL (
  SELECT round(t.items_total * CASE o2.coupon_code
      WHEN 'FLAT10' THEN 0.10 WHEN 'WELCOME15' THEN 0.15 WHEN 'KARTLY20' THEN 0.20
      WHEN 'EOSS25' THEN 0.25 WHEN 'APPONLY5' THEN 0.05 ELSE 0 END, 2) AS coupon,
    CASE WHEN t.items_total >= 999 THEN 0
         WHEN o2.city_tier = 'tier_3' THEN 79 ELSE 49 END::numeric AS ship
  FROM orders o2 WHERE o2.order_id = t.order_id
) c
WHERE o.order_id = t.order_id;

ANALYZE;
