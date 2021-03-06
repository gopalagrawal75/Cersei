from . import basic_success, basic_failure, basic_error, db
from datetime import datetime

def item_list(opts, vendor_id, method):
	if method != "GET":
		return basic_failure("GET method only")
	store_id = opts['vendor_id']
	if store_id:
		try:
			return basic_success(db.items_alt.find({"store_id" :int(store_id)} , {"_id":False}))
		except:
			return basic_error("Invalid Store ID");
	else:
		return basic_error("Store id is not available");
	
	
def order_list(opts, vendor_id, method):
	if method != "GET":
		return basic_failure("GET method only")

    # Get the status required
	status = opts.get("status")
	# Data fetch from db
	if status:
		data = list(db.orders.aggregate([
			{"$match": {
				"vendor_id": vendor_id,
				"status.0.status": status
				
			}},
			{"$sort": {"timestamp": -1}},
			{"$project": {
				"_id": 0,
				"order_id": 1,
				"status": "$status.status",
				"pts":1,
				"address": 1,
				"timestamp": 1,
				"order.qty": 1,
				"order.price": 1
			}}
		]))
	else:
		data = list(db.orders.aggregate([
			{"$match": {
				"vendor_id": vendor_id,
				"status.0.status": status
				
			}},
			{"$sort": {"timestamp": -1}},
			{"$project": {
				"_id": 0,
				"order_id": 1,
				"status": "$status.status",
				"address": 1,
				"timestamp": 1,
				"pts":1,
				"order.qty": 1,
				"order.price": 1
			}}
		]))
    # Transform the data to get the price and stuff, todo: debatable
	for record in data:
		record['status'] = record['status'][0]
		order = record.pop('order')
		record['price'] = 0
		record['item_count'] = 0
		for item in order:
			record['price'] += item['price']
			record['item_count'] += item['qty']

	return basic_success(data)


def update_order(opts, vendor_id, method):
    if method != "POST":
        return basic_failure("POST method only")

    status = opts['status']
    order_id = opts['order_id']

    push_query = {
        "status": {
            "$each": [{"status": status, "time": datetime.now()}],
            "$position": 0
        }
    }

    if status == "cancelled":
        db.orders.update_one({"order_id": order_id, "vendor_id": vendor_id}, {"$push": push_query})
        return basic_success()
    elif status == "accepted":
        data = db.orders.find_one({"order_id": order_id, "vendor_id": vendor_id})
        if not data:
            return basic_failure("Ghost Order")
        order_codes = opts['order_codes']   # This should be a single array
        order = data['order']

        # We will recheck the codes and all
        # 1. Get data for each code
        code_data = list(db.codes.find({
            "code": {"$in": order_codes},
            "used": False
        }, {"_id": False}))

        # 2. match items against codes
        pts = 0
        for item in order:
            item['codes'] = []
            icodes = filter(lambda cd: cd['barcode'] == item['barcode'], code_data)
            for code in icodes:
                if len(item['codes']) == item['qty']:
                    break
                item['codes'].append(code['code'])
                pts += code['pts']
                db.codes.update_one({"code": code['code']}, {"$set": {"used": True}})
        # 3. update order
        db.orders.update_one({"_id": data['_id']}, {
            "$set": {
                "order": order,
                "pts": pts
            },
            "$push": push_query
        })
        return basic_success(pts)


def inner_scan(opts, vendor_id, method):
	code = opts.get("code")
	order_id = opts.get("order_id")
	if not code or not order_id:
		return basic_error("Invalid parameters")
	code_data = db.codes_alt.find_one({"code": code}, {"_id": False })
	if not code_data:
		return basic_failure("Code not found")
	if code_data['used']:
		return basic_failure("Already used")
	qrcodes=db.orders.find_one({"order_id":order_id} , {"_id":False , "order":True})
	barcodes=list()
	for qrcode in qrcodes['order']:
		barcodes.append(qrcode['barcode'])
	offer = db.offers_alt.find_one({"offer_id":int(code_data['offer_id'])})
	item = db.items_alt.find_one({"item_id": offer['item_id']}, {"_id": False, "name": 1, "barcode": 1,"price":1, "img":1 , "weight":1})
	if item['barcode'] in barcodes:
		return basic_success({
			"code": code,
			"pts": offer['points'],
			"item": item,
			"codematch":True
		})
	else:
		return basic_success({
			"code": code,
			"pts": offer['points'],
			"item": item,
			"codematch":False
		})

def new_scan(opts, vendor_id, method):
	code = opts.get("code")
	if not code:
		return basic_error("No code given")
	data = db.codes_alt.find_one({"code": code, "used": False}, {"code": True, "offer_id": True, "_id": False})
	if not data:
		return basic_failure("Already Used")
	else:
		offer = db.offers_alt.find_one({"offer_id":int(data['offer_id'])})
		item = db.items_alt.find_one({"item_id": offer['item_id']}, {"_id": False, "name": 1, "barcode": 1,"price":1, "img":1 , "weight":1})
		return basic_success({
			"code": code,
			"pts": offer['points'],
			"item": item
			
		})
