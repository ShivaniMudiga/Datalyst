-- Money, logistics, returns and acquisition. Everything here derives from the
-- orders seeded in 02, so the funnel adds up: a payment that never captured
-- cancels its order, an RTO shipment marks its order returned, a return
-- produces a refund against the payment that actually took the money.

-- ---------------------------------------------------------------- payments
-- Prepaid orders retry on failure. Success depends on the instrument and the
-- gateway, which is the whole point of having three gateways in the data.
CREATE TEMP TABLE pay_try AS
SELECT
  o.order_id, a AS attempt_no, o.payment_method, o.order_total, o.placed_at,
  (ARRAY['razorpay','razorpay','razorpay','payu','cashfree'])[1 + floor(rnd(o.order_id || ':gw') * 5)::int] AS gateway,
  rnd(o.order_id || ':pay:' || a) AS r
FROM orders o, generate_series(1, 3) a
WHERE NOT o.is_cod;

CREATE TEMP TABLE pay_scored AS
SELECT t.*,
  CASE WHEN attempt_no = 1
       THEN LEAST(0.9, (1 - CASE payment_method
              WHEN 'upi' THEN 0.93 WHEN 'credit_card' THEN 0.86 WHEN 'debit_card' THEN 0.82
              WHEN 'netbanking' THEN 0.79 WHEN 'wallet' THEN 0.94 ELSE 0.77 END)
            * CASE gateway WHEN 'razorpay' THEN 0.82 WHEN 'payu' THEN 1.45 ELSE 1.08 END)
       WHEN attempt_no = 2 THEN 0.28
       ELSE 0.40 END AS fail_prob
FROM pay_try t;

CREATE TEMP TABLE pay_kept AS
SELECT z.*, min(attempt_no) FILTER (WHERE ok) OVER (PARTITION BY order_id) AS first_ok
FROM (SELECT s.*, (r > fail_prob) AS ok FROM pay_scored s) z;

INSERT INTO payments (order_id, attempt_no, gateway, payment_method, bank_name, amount,
                      payment_status, failure_reason, initiated_at, captured_at, gateway_fee)
SELECT
  k.order_id, k.attempt_no, k.gateway, k.payment_method,
  CASE WHEN k.payment_method IN ('credit_card','debit_card','netbanking','emi')
       THEN (ARRAY['HDFC Bank','ICICI Bank','State Bank of India','Axis Bank','Kotak Mahindra',
                   'Yes Bank','IDFC First','Punjab National Bank'])[1 + floor(rnd(k.order_id || ':bank') * 8)::int] END,
  k.order_total,
  CASE WHEN k.ok THEN 'captured' ELSE 'failed' END,
  CASE WHEN k.ok THEN NULL ELSE (ARRAY['insufficient_funds','bank_declined','gateway_timeout',
        'otp_not_entered','risk_flagged','upi_app_closed'])[1 + floor(rnd(k.order_id || ':fr:' || k.attempt_no) * 6)::int] END,
  k.placed_at + make_interval(secs => (k.attempt_no - 1) * 95 + floor(rnd(k.order_id || ':t:' || k.attempt_no) * 40)::int),
  CASE WHEN k.ok THEN k.placed_at + make_interval(secs => (k.attempt_no - 1) * 95 + 12) END,
  CASE WHEN NOT k.ok THEN 0
       WHEN k.payment_method = 'upi' THEN 0
       WHEN k.payment_method IN ('credit_card','emi') THEN round(k.order_total * 0.0212, 2)
       WHEN k.payment_method = 'debit_card' THEN round(k.order_total * 0.0094, 2)
       ELSE round(k.order_total * 0.0177, 2) END
FROM pay_kept k
WHERE k.attempt_no <= COALESCE(k.first_ok,
        CASE WHEN rnd(k.order_id || ':giveup') < 0.62 THEN 1 ELSE 2 END);

-- A prepaid order whose payment never captured is a lost sale, not an order.
UPDATE orders o SET order_status = 'cancelled'
WHERE NOT o.is_cod
  AND NOT EXISTS (SELECT 1 FROM payments p WHERE p.order_id = o.order_id AND p.payment_status = 'captured');

-- --------------------------------------------------------------- shipments
INSERT INTO shipments (order_id, courier, warehouse, shipped_at, promised_by, delivered_at,
                       shipment_status, is_rto, shipping_cost)
SELECT
  o.order_id,
  (ARRAY['Delhivery','Delhivery','Bluedart','Ekart','XpressBees','Shadowfax','India Post'])[1 + floor(rnd(o.order_id || ':cr') * 7)::int],
  (ARRAY['Bhiwandi FC','Bengaluru FC','Gurugram FC','Kolkata FC','Hyderabad FC'])[1 + floor(rnd(o.order_id || ':wh') * 5)::int],
  CASE WHEN s.cancelled THEN NULL ELSE o.placed_at + make_interval(hours => s.dispatch_h) END,
  o.placed_at + make_interval(days => s.promise_d),
  CASE WHEN s.cancelled OR s.rto THEN NULL
       WHEN o.placed_at + make_interval(hours => s.dispatch_h + s.transit_h) > now() THEN NULL
       ELSE o.placed_at + make_interval(hours => s.dispatch_h + s.transit_h) END,
  CASE WHEN s.cancelled THEN 'cancelled'
       WHEN s.rto THEN 'rto'
       WHEN o.placed_at + make_interval(hours => s.dispatch_h + s.transit_h) > now() THEN 'in_transit'
       ELSE 'delivered' END,
  s.rto,
  round((38 + s.transit_h * 0.42 + CASE WHEN o.is_cod THEN 15 ELSE 0 END)::numeric, 2)
FROM orders o
CROSS JOIN LATERAL (
  SELECT
    rnd(o.order_id || ':cnl') < 0.038 AS cancelled,
    rnd(o.order_id || ':rto') < (0.040 * CASE WHEN o.is_cod THEN 2.4 ELSE 1 END
                                        * CASE o.city_tier WHEN 'tier_3' THEN 1.7 WHEN 'tier_2' THEN 1.25 ELSE 1 END) AS rto,
    6 + floor(rnd(o.order_id || ':dsp') * 34)::int AS dispatch_h,
    CASE o.city_tier WHEN 'tier_1' THEN 3 WHEN 'tier_2' THEN 5 ELSE 7 END AS promise_d,
    (CASE o.city_tier WHEN 'tier_1' THEN 30 WHEN 'tier_2' THEN 54 ELSE 84 END
      + floor(rnd(o.order_id || ':trn') * CASE o.city_tier WHEN 'tier_1' THEN 62 WHEN 'tier_2' THEN 96 ELSE 132 END))::int AS transit_h
) s
WHERE o.order_status <> 'cancelled';

UPDATE orders o SET order_status = CASE s.shipment_status
    WHEN 'cancelled' THEN 'cancelled'
    WHEN 'rto'       THEN 'returned'
    WHEN 'in_transit' THEN CASE WHEN s.shipped_at IS NULL OR now() - o.placed_at < interval '18 hours'
                                THEN 'pending' ELSE 'shipped' END
    ELSE 'delivered' END
FROM shipments s WHERE s.order_id = o.order_id;

-- COD money only exists once the courier collects it.
INSERT INTO payments (order_id, attempt_no, gateway, payment_method, amount,
                      payment_status, failure_reason, initiated_at, captured_at, gateway_fee)
SELECT o.order_id, 1, 'cod_collection', 'cod', o.order_total,
  CASE WHEN s.delivered_at IS NOT NULL THEN 'captured'
       WHEN s.shipment_status IN ('rto','cancelled') THEN 'failed' ELSE 'pending' END,
  CASE WHEN s.shipment_status = 'rto' THEN 'rto_uncollected'
       WHEN s.shipment_status = 'cancelled' THEN 'order_cancelled' END,
  o.placed_at, s.delivered_at,
  CASE WHEN s.delivered_at IS NOT NULL THEN round(o.order_total * 0.0155, 2) ELSE 0 END
FROM orders o JOIN shipments s ON s.order_id = o.order_id
WHERE o.is_cod;

-- ----------------------------------------------------------------- returns
-- Return rate is a property of the category: apparel sizing drives most of it,
-- beauty and home barely return at all.
INSERT INTO returns (order_id, order_item_id, return_reason, return_status, refund_amount, initiated_at, resolved_at)
SELECT
  oi.order_id, oi.order_item_id,
  CASE WHEN r.rr < 0.40 THEN 'size_issue'    WHEN r.rr < 0.56 THEN 'changed_mind'
       WHEN r.rr < 0.72 THEN 'quality_issue' WHEN r.rr < 0.83 THEN 'damaged_in_transit'
       WHEN r.rr < 0.93 THEN 'wrong_item_sent' ELSE 'late_delivery' END,
  CASE WHEN s.delivered_at + make_interval(days => r.init_d + r.resolve_d) > now() THEN 'processing' ELSE 'refunded' END,
  oi.line_total,
  s.delivered_at + make_interval(days => r.init_d),
  CASE WHEN s.delivered_at + make_interval(days => r.init_d + r.resolve_d) > now() THEN NULL
       ELSE s.delivered_at + make_interval(days => r.init_d + r.resolve_d) END
FROM order_items oi
JOIN orders o  ON o.order_id = oi.order_id AND o.order_status = 'delivered'
JOIN shipments s ON s.order_id = oi.order_id AND s.delivered_at IS NOT NULL
JOIN products p ON p.product_id = oi.product_id
CROSS JOIN LATERAL (
  SELECT rnd(oi.order_item_id || ':ret') AS rp, rnd(oi.order_item_id || ':rr') AS rr,
         1 + floor(rnd(oi.order_item_id || ':ri') * 11)::int AS init_d,
         2 + floor(rnd(oi.order_item_id || ':rs') * 7)::int AS resolve_d
) r
WHERE r.rp < 0.095 * CASE
    WHEN p.category IN ('Women Western Wear','Men Bottomwear') THEN 1.45
    WHEN p.category IN ('Women Ethnic Wear','Men Topwear')     THEN 1.20
    WHEN p.category = 'Footwear'                               THEN 1.30
    WHEN p.category = 'Accessories'                            THEN 0.70
    ELSE 0.38 END;

UPDATE order_items oi SET item_status = 'returned'
FROM returns r WHERE r.order_item_id = oi.order_item_id;

UPDATE orders o SET order_status = 'returned'
WHERE order_status = 'delivered'
  AND EXISTS (SELECT 1 FROM returns r WHERE r.order_id = o.order_id);

UPDATE order_items oi SET item_status = o.order_status
FROM orders o WHERE o.order_id = oi.order_id
  AND oi.item_status = 'ordered' AND o.order_status IN ('cancelled','delivered','shipped');

-- ----------------------------------------------------------------- refunds
INSERT INTO refunds (payment_id, order_id, amount, refund_reason, refund_status, initiated_at, settled_at)
SELECT p.payment_id, r.order_id, r.refund_amount, r.return_reason,
  CASE WHEN r.resolved_at IS NULL THEN 'processing' ELSE 'settled' END,
  COALESCE(r.resolved_at, now()) - interval '1 day',
  r.resolved_at + make_interval(days => 1 + floor(rnd(r.return_id || ':rf') * 4)::int)
FROM returns r
JOIN LATERAL (SELECT payment_id FROM payments WHERE order_id = r.order_id AND payment_status = 'captured'
              ORDER BY attempt_no DESC LIMIT 1) p ON true;

INSERT INTO refunds (payment_id, order_id, amount, refund_reason, refund_status, initiated_at, settled_at)
SELECT p.payment_id, o.order_id, o.order_total, 'order_cancelled', 'settled',
  o.placed_at + interval '1 day', o.placed_at + interval '4 days'
FROM orders o
JOIN LATERAL (SELECT payment_id FROM payments WHERE order_id = o.order_id AND payment_status = 'captured'
              ORDER BY attempt_no DESC LIMIT 1) p ON true
WHERE o.order_status = 'cancelled' AND NOT o.is_cod;

-- ----------------------------------------------------------------- reviews
INSERT INTO product_reviews (product_id, customer_id, order_id, rating, review_text, created_at)
SELECT oi.product_id, o.customer_id, o.order_id,
  CASE WHEN oi.item_status = 'returned'
       THEN 1 + floor(rnd(oi.order_item_id || ':rt') * 3)::int
       ELSE CASE WHEN rnd(oi.order_item_id || ':rt2') < 0.58 THEN 5
                 WHEN rnd(oi.order_item_id || ':rt2') < 0.84 THEN 4
                 WHEN rnd(oi.order_item_id || ':rt2') < 0.94 THEN 3 ELSE 2 END END,
  (ARRAY['Exactly as described.','Fabric quality is decent for the price.','Size ran smaller than the chart.',
         'Delivery was quick, packaging was good.','Colour is different from the photos.',
         'Worth it during the sale.','Stitching came apart after two washes.','Would buy again.'])[1 + floor(rnd(oi.order_item_id || ':rx') * 8)::int],
  s.delivered_at + make_interval(days => 2 + floor(rnd(oi.order_item_id || ':rd') * 12)::int)
FROM order_items oi
JOIN orders o ON o.order_id = oi.order_id
JOIN shipments s ON s.order_id = oi.order_id AND s.delivered_at IS NOT NULL
WHERE rnd(oi.order_item_id || ':rv') < 0.21;

-- --------------------------------------------------------- marketing spend
INSERT INTO marketing_spend (spend_date, channel, campaign, impressions, clicks, spend_amount)
SELECT d::date, ch.channel,
  ch.channel || '_' || to_char(d, 'YYYY_MM') || '_' || ch.tag,
  imp::bigint, (imp * ch.ctr)::int, round((imp / 1000.0 * ch.cpm)::numeric, 2)
FROM generate_series(DATE '2024-09-01', DATE '2026-08-30', INTERVAL '1 day') d
CROSS JOIN (VALUES
  ('google_ads','search', 210.0, 0.031, 0.34),
  ('meta_ads','prospecting', 165.0, 0.019, 0.28),
  ('meta_ads','retargeting', 240.0, 0.042, 0.11),
  ('influencer','creators', 95.0, 0.012, 0.18),
  ('affiliate','network', 70.0, 0.026, 0.07),
  ('email','lifecycle', 12.0, 0.085, 0.02)
) AS ch(channel, tag, cpm, ctr, share)
CROSS JOIN LATERAL (
  SELECT (900000 * ch.share
      * (0.75 + 0.55 * (d::date - DATE '2024-09-01') / 729.0)
      * CASE extract(month FROM d) WHEN 10 THEN 2.4 WHEN 1 THEN 1.7 WHEN 7 THEN 1.6
                                   WHEN 11 THEN 1.3 ELSE 1.0 END
      * (0.85 + rnd(d || ch.channel || ch.tag) * 0.3))::bigint AS imp
) m;

-- ---------------------------------------------------------------- sessions
-- Roughly ten sessions per order placed that day: browsing is the top of the
-- funnel that marketing spend is actually buying.
INSERT INTO web_sessions (customer_id, started_at, device, channel, landing_page, pages_viewed, added_to_cart, converted, session_secs)
SELECT
  CASE WHEN v.anon < 0.36 THEN NULL ELSE 1 + floor(v.anon * 26000)::int END,
  d.day + make_interval(hours => floor(v.h * 24)::int, mins => floor(v.m * 60)::int),
  CASE WHEN v.dev < 0.58 THEN 'android' WHEN v.dev < 0.79 THEN 'ios'
       WHEN v.dev < 0.93 THEN 'mobile_web' ELSE 'desktop' END,
  CASE WHEN v.ch < 0.31 THEN 'organic' WHEN v.ch < 0.52 THEN 'google_ads'
       WHEN v.ch < 0.71 THEN 'meta_ads' WHEN v.ch < 0.81 THEN 'influencer'
       WHEN v.ch < 0.90 THEN 'affiliate' WHEN v.ch < 0.96 THEN 'email' ELSE 'referral' END,
  CASE WHEN v.lp < 0.34 THEN '/home' WHEN v.lp < 0.58 THEN '/category' WHEN v.lp < 0.80 THEN '/product'
       WHEN v.lp < 0.90 THEN '/search' ELSE '/offers' END,
  1 + floor(power(v.pv, 1.8) * 24)::int,
  v.cart < 0.23,
  v.cart < 0.23 AND v.conv < 0.44,
  20 + floor(power(v.pv, 1.5) * 900)::int
FROM (SELECT placed_at::date AS day, count(*) AS orders FROM orders GROUP BY 1) d
CROSS JOIN LATERAL generate_series(1, d.orders * 10) n
CROSS JOIN LATERAL (
  SELECT rnd(d.day || ':a:' || n) AS anon, rnd(d.day || ':h:' || n) AS h, rnd(d.day || ':m:' || n) AS m,
         rnd(d.day || ':d:' || n) AS dev, rnd(d.day || ':c:' || n) AS ch, rnd(d.day || ':l:' || n) AS lp,
         rnd(d.day || ':p:' || n) AS pv, rnd(d.day || ':k:' || n) AS cart, rnd(d.day || ':v:' || n) AS conv
) v;

ANALYZE;
