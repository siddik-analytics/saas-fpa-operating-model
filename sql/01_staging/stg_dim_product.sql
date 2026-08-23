-- Staging: typed pass-through of dim_product. No business logic.
select
    product_id,
    product_name,
    product_type,
    pricing_model,
    cast(list_price_monthly as decimal(18, 2)) as list_price_monthly,
    is_core
from raw_dim_product
