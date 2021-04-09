def calculate_item_price(item):
    """ Calculates item price

    Args:
        item (dict): Item from GraphQl Order

    Returns:
        price (float): Price

    Note:
        item in form of
        {
            "listPrice": "89.40",
            "itemDiscounts": "0.00",
            "orderDiscounts": "0.00"
        }
    """
    item_discounts = float(item.get("itemDiscounts", "0") or "0") # unsure if 0.00 is always returned when not applied
    order_discounts = float(item.get("orderDiscounts", "0") or "0") # unsure if 0.00 is always returned when not applied
    list_price = float(item.get("listPrice"))
    discount = float("{:.2f}".format(item_discounts + order_discounts))
    return float("{:.2f}".format(list_price - discount))
