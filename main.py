from flask import Flask, request, session
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from google.cloud import datastore
import math
import datetime
import credentials as cred

app = Flask(__name__)
app.config.from_object(__name__)
app.config['SECRET_KEY'] = cred.get_secret_key()
@app.route("/sms", methods=['GET', 'POST'])
def conversation_processor():
    account_sid = cred.get_account_sid()
    auth_token = cred.get_auth_token()
    mess_client = Client(account_sid, auth_token)
    client = datastore.Client('speedie-bean-twilio')

    counter = session.get('counter', 0)
    counter += 1
    session['counter'] = counter

    number = request.form['From']
    message_body = request.form['Body']

    resp = MessagingResponse()

    if (message_body.lower() == "reload") and ((
        number == cred.get_isaac_number()) or (
        number == cred.get_jack_number())):
        return reload()

    elif (message_body.lower() == "remove morning") and ((
        number == cred.get_isaac_number()) or (
        number == cred.get_jack_number())):
        return remove('9:00am-12:00pm')

    elif (message_body.lower() == "remove afternoon") and ((
        number == cred.get_isaac_number()) or (
        number == cred.get_jack_number())):
        return remove('2:00pm-5:00pm')

    elif (message_body.lower() == "remove evening") and ((
        number == cred.get_isaac_number()) or (
        number == cred.get_jack_number())):
        return remove('7:00pm-9:00pm')

    if message_body.lower() == "restart":
        restart(number)

    elif message_body.lower() == "cancel order":
        return cancel_order(number)

    if session.get('counter', 0) == 1:
        query = client.query(kind='Orders')
        query.add_filter('number', '=', number)
        orders = list(query.fetch())
        if len(orders) > 5:
            min_time_stamp = datetime.datetime(int(orders[0]['year']), int(orders[0]['month']), int(orders[0]['day']), int(orders[0]['hour']), int(orders[0]['minute']))
            minimum = 0
            for i in range(1, len(orders)):
                time_stamp = datetime.datetime(int(orders[i]['year']), int(orders[i]['month']), int(orders[i]['day']), int(orders[i]['hour']), int(orders[i]['minute']))
                if time_stamp < min_time_stamp:
                    min_time_stamp = time_stamp
                    minimum = i
            old_order = orders[minimum]
            orders = orders[:minimum] + orders[(minimum + 1):]
            client.delete(old_order.key)
        if ((message_body.lower() == "coffee") or (
            message_body.lower() == "restart")) and (len(orders) != 0):
            order_list = "0)\nNew order\n\n"
            for i in range(len(orders)):
                current = orders[i]
                order_i = "%d)\nname: %s\nAddress: %s\nLarges: %s\nSmalls: %s\n\n" % (i + 1, current['name'], current['address'], current['half_gallons'], current['quarts'])
                order_list += order_i
            resp.message("Welcome back to Speedie Bean!" \
                + " Choose an existing order below by responding with its order number or " \
                + "respond with 0 to create a new order.\n\n" \
                + order_list + "\n(Type \"Restart\" anytime to restart your order or type \"Cancel order\" to cancel your order.)")
            customer = 'return'
            session['customer'] = customer
        elif ((message_body.lower() == "coffee") or (
            message_body.lower() == "restart")) and (len(orders) == 0):
            resp.message("Welcome to Speedie Bean!" \
                + " We deliver cold brew coffee to Tulane's campus and the surrounding area." \
                + " Please respond with your name to start an order.\n\n"
                + "(Type \"Restart\" anytime to restart your order or type \"Cancel order\" to cancel your order.)")
            customer = 'new'
            session['customer'] = customer
        else:
            counter -= 1
            session['counter'] = counter
            resp.message("Text COFFEE to place an order.")
        return str(resp)

    elif session.get('counter', 0) == 2:
        if session.get('customer') == 'return':
            query = client.query(kind='Orders')
            query.add_filter('number', '=', number)
            orders = list(query.fetch())
            try:
                num = int(message_body)
                if (num <= len(orders)) and (
                    num >= 1) and (
                    math.floor(num) == num):
                    query = client.query(kind='Orders')
                    query.add_filter('number', '=', number)
                    orders = list(query.fetch())
                    order = datastore.Entity(client.key('Placed'))
                    order.update({
                        'number': number, \
                        'address': orders[int(message_body) - 1]['address'], \
                        'name': orders[int(message_body) - 1]['name'], \
                        'quarts': orders[int(message_body) - 1]['quarts'], \
                        'half_gallons': orders[int(message_body) - 1]['half_gallons'], \
                        'time': 'new' \
                    })
                    client.put(order)
                    chosen = orders[int(message_body) - 1]
                    query = client.query(kind='Time')
                    query.add_filter('slots', '>', 0)
                    times = list(query.fetch())
                    resp.message(list_times(chosen, times))
                    if len(times) == 0:
                        return str(resp)
                    placed = 'yes'
                    session['placed'] = placed
                elif num == 0:
                    resp.message("Please respond with your name.")
                    placed = 'no'
                    session['placed'] = placed
                else:
                    counter -= 1
                    session['counter'] = counter
                    resp.message("Please respond with a number 0 through %d." % len(orders))
            except ValueError:
                counter -= 1
                session['counter'] = counter
                resp.message("Please respond with a number 0 through %d." % len(orders))
                print("Could not convert response to integer.")
        elif session.get('customer') == 'new':
            order = datastore.Entity(client.key('Orders'))
            order.update({
                'number': number, \
                'name': message_body, \
                'address': "1000223", \
                'half_gallons': 1000223, \
                'quarts': 1000223
            })
            client.put(order)
            resp.message("Our delicious cold brew coffee comes in Small (32oz) and Large (64oz) sizes." \
                + " First, tell us how many Small coffees you would like. If you don't want any, respond with 0.")
            placed = 'no'
            session['placed'] = placed
        return str(resp)

    elif session.get('counter', 0) == 3:
        if session.get('placed') == 'no' and session.get('customer') == 'new':
            try:
                if int(message_body) < 0:
                    counter -= 1
                    session['counter'] = counter
                    resp.message("Please respond with a positive integer value for the desired number of Smalls.")
                    return str(resp)
                query = client.query(kind='Orders')
                query.add_filter('number', '=', number)
                query.add_filter('address', '=', '1000223')
                new_order = list(query.fetch())
                updated_order = new_order[0]
                updated_order.update({'quarts': int(message_body)})
                client.put(updated_order)
                resp.message("Next, please tell us how many Large coffees you would like.")
                placed = 'no'
                session['placed'] = placed
            except ValueError:
                counter -= 1
                session['counter'] = counter
                resp.message("Please respond with a positive integer value for the desired number of Smalls.")
                print("Could not convert response to integer.")
        elif session.get('placed') == 'no' and session.get('customer') == 'return':
            order = datastore.Entity(client.key('Orders'))
            order.update({
                'number': number, \
                'name': message_body, \
                'address': "1000223", \
                'half_gallons': 1000223, \
                'quarts': 1000223
            })
            client.put(order)
            resp.message("Our delicious cold brew coffee comes in Small (32oz) and Large (64oz) sizes." \
                + " First, tell us how many Small coffees you would like. If you don't want any, respond with 0.")
            placed = 'no'
            session['placed'] = placed
        elif session.get('placed') == 'yes':
            if message_body.lower() == "asap":
                resp.message(asap())
                return str(resp)
            converted_time = time_format(message_body)
            time_valid = valid_time(converted_time, client, mess_client)
            if converted_time == False:
                resp.message("Please enter a time in the correct format.\n\nExample:\n10:00am")
                counter -= 1
                session['counter'] = counter
                return str(resp)
            if time_valid == False:
                resp.message("Time format entered is correct but please enter a future time within the available timeslots.")
                counter -= 1
                session['counter'] = counter
                return str(resp)
            if time_valid == 'morning':
                decrement_slot('9:00am-12:00pm')
            elif time_valid == 'afternoon':
                decrement_slot('2:00pm-5:00pm')
            elif time_valid == 'evening':
                decrement_slot('7:00pm-9:00pm')
            query = client.query(kind='Placed')
            query.add_filter('number', '=', number)
            query.add_filter('time', '=', 'new')
            new_order = list(query.fetch())
            updated_order = new_order[0]
            utc_now = datetime.datetime.now(datetime.timezone.utc)
            current_hour = utc_now.hour - 6
            if current_hour < 0:
                current_hour += 24
            now = datetime.datetime(utc_now.year, utc_now.month, utc_now.day, current_hour, utc_now.minute, utc_now.second, utc_now.microsecond)
            updated_order.update({
                'time': message_body, \
                'time_ordered': str(now)})
            message = mess_client.messages.create(
                body='number: %s, name: %s, address: %s, time: %s, half gallons: %d, quarts: %d' % (number, updated_order['name'], \
                    updated_order['address'], updated_order['time'], \
                    int(updated_order['half_gallons']), int(updated_order['quarts'])),
                from_=cred.get_speedie_number(),
                to=cred.get_common_number()
            )
            print(message.sid)
            resp.message("Thank you for your order! We'll bring your coffee at %s. You will be contacted by the delivery team for updates.\n\nText COFFEE at any time to place another order.\n\nThank you for being a beta tester for our ordering software. If you feel like you have exhausted the capabilites of the software and have tested it thoroughly, we would really appreciate it if you would out the survey below to let us know how it worked for you. Thanks again!\nhttps://tulane.co1.qualtrics.com/jfe/form/SV_1Y3KPGKY2UYo3ul" % updated_order['time'])
            client.put(updated_order)
            placed = 'no'
            session['placed'] = placed
            customer = 'new'
            session['customer'] = customer
            counter = 0
            session['counter'] = counter
        return str(resp)

    elif session.get('counter', 0) == 4:
        if session.get('placed') == 'no' and session.get('customer') == 'new':
            try:
                if int(message_body) < 0:
                    counter -= 1
                    session['counter'] = counter
                    resp.message("Please respond with a positive integer value for the desired number of Larges.")
                    return str(resp)
                query = client.query(kind='Orders')
                query.add_filter('number', '=', number)
                query.add_filter('address', '=', '1000223')
                new_order = list(query.fetch())
                updated_order = new_order[0]
                updated_order.update({'half_gallons': int(message_body)})
                client.put(updated_order)
                resp.message("Where do you want your coffee delivered?\n" \
                    + "(This can be an address or building on campus)")
                placed = 'no'
                session['placed'] = placed
            except ValueError:
                counter -= 1
                session['counter'] = counter
                resp.message("Please respond with a positive integer value for the desired number of Larges.")
                print("Could not convert response to integer.")
        elif session.get('placed') == 'no' and session.get('customer') == 'return':
            try:
                if int(message_body) < 0:
                    counter -= 1
                    session['counter'] = counter
                    resp.message("Please respond with a positive integer value for the desired number of Smalls.")
                    return str(resp)
                query = client.query(kind='Orders')
                query.add_filter('number', '=', number)
                query.add_filter('address', '=', '1000223')
                new_order = list(query.fetch())
                updated_order = new_order[0]
                updated_order.update({'quarts': int(message_body)})
                client.put(updated_order)
                resp.message("Next, please tell us how many Larges you would like.")
                placed = 'no'
                session['placed'] = placed
            except ValueError:
                counter -= 1
                session['counter'] = counter
                resp.message("Please respond with an integer value for the desired number of Smalls.")
                print("Could not convert response to integer.")
        return str(resp)

    elif session.get('counter', 0) == 5:
        if session.get('placed') == 'no' and session.get('customer') == 'new':
            query = client.query(kind='Orders')
            query.add_filter('number', '=', number)
            query.add_filter('address', '=', '1000223')
            new_order = list(query.fetch())
            updated_order = new_order[0]
            utc_now = datetime.datetime.now(datetime.timezone.utc)
            current_hour = utc_now.hour - 6
            if current_hour < 0:
                current_hour += 24
            now = datetime.datetime(utc_now.year, utc_now.month, utc_now.day, current_hour, utc_now.minute, utc_now.second, utc_now.microsecond)
            updated_order.update({
                'address': message_body, \
                'year': now.year, \
                'month': now.month, \
                'day': now.day, \
                'hour': now.hour, \
                'minute': now.minute})
            placed_order = datastore.Entity(client.key('Placed'))
            placed_order.update({
                'number': number, \
                'name': updated_order['name'], \
                'address': updated_order['address'], \
                'half_gallons': updated_order['half_gallons'], \
                'quarts': updated_order['quarts'], \
                'time': 'new' \
            })
            query = client.query(kind='Time')
            query.add_filter('slots', '>', 0)
            times = list(query.fetch())
            resp.message(list_times(updated_order, times))
            if len(times) == 0:
                return str(resp)
            client.put(updated_order)
            client.put(placed_order)
            placed = 'yes'
            session['placed'] = placed
        elif session.get('placed') == 'no' and session.get('customer') == 'return':
            try:
                if int(message_body) < 0:
                    counter -= 1
                    session['counter'] = counter
                    resp.message("Please respond with a positive integer value for the desired number of Larges.")
                    return str(resp)
                query = client.query(kind='Orders')
                query.add_filter('number', '=', number)
                query.add_filter('address', '=', '1000223')
                new_order = list(query.fetch())
                updated_order = new_order[0]
                updated_order.update({'half_gallons': int(message_body)})
                client.put(updated_order)
                resp.message("Where do you want your coffee delivered?\n" \
                    + "(This can be an address or building on campus)")
                placed = 'no'
                session['placed'] = placed
            except ValueError:
                counter -= 1
                session['counter'] = counter
                resp.message("Please respond with an integer value for the desired number of Larges.")
        return str(resp)

    elif session.get('counter', 0) == 6:
        if session.get('placed') == 'yes' and session.get('customer') == 'new':
            if message_body.lower() == "asap":
                resp.message(asap())
                return str(resp)
            converted_time = time_format(message_body)
            time_valid = valid_time(converted_time, client, mess_client)
            if converted_time == False:
                resp.message("Please enter a time in the correct format.\n\nExample:\n10:00am")
                counter -= 1
                session['counter'] = counter
                return str(resp)
            if time_valid == False:
                resp.message("Time format entered is correct but please enter a future time within the available timeslots.")
                counter -= 1
                session['counter'] = counter
                return str(resp)
            if time_valid == 'morning':
                decrement_slot('9:00am-12:00pm')
            elif time_valid == 'afternoon':
                decrement_slot('2:00pm-5:00pm')
            elif time_valid == 'evening':
                decrement_slot('7:00pm-9:00pm')
            query = client.query(kind='Placed')
            query.add_filter('number', '=', number)
            query.add_filter('time', '=', 'new')
            new_order = list(query.fetch())
            updated_order = new_order[0]
            utc_now = datetime.datetime.now(datetime.timezone.utc)
            current_hour = utc_now.hour - 6
            if current_hour < 0:
                current_hour += 24
            now = datetime.datetime(utc_now.year, utc_now.month, utc_now.day, current_hour, utc_now.minute, utc_now.second, utc_now.microsecond)
            updated_order.update({
                'time': message_body, \
                'time_ordered': str(now)})
            message = mess_client.messages.create(
                body='number: %s, name: %s, address: %s, time: %s, half gallons: %d, quarts: %d' % (number, updated_order['name'], \
                    updated_order['address'], updated_order['time'], \
                    int(updated_order['half_gallons']), int(updated_order['quarts'])),
                from_=cred.get_speedie_number(),
                to=cred.get_common_number()
            )
            print(message.sid)
            resp.message("Thank you for your order! We'll bring your coffee at %s. You will be contacted by the delivery team for updates.\n\nText COFFEE at any time to place another order.\n\nThank you for being a beta tester for our ordering software. If you feel like you have exhausted the capabilites of the software and have tested it thoroughly, we would really appreciate it if you would out the survey below to let us know how it worked for you. Thanks again!\nhttps://tulane.co1.qualtrics.com/jfe/form/SV_1Y3KPGKY2UYo3ul" % updated_order['time'])
            client.put(updated_order)
            placed = 'no'
            session['placed'] = placed
            customer = 'new'
            session['customer'] = customer
            counter = 0
            session['counter'] = counter
        elif session.get('placed') == 'no' and session.get('customer') == 'return':
            query = client.query(kind='Orders')
            query.add_filter('number', '=', number)
            query.add_filter('address', '=', '1000223')
            new_order = list(query.fetch())
            updated_order = new_order[0]
            utc_now = datetime.datetime.now(datetime.timezone.utc)
            current_hour = utc_now.hour - 6
            if current_hour < 0:
                current_hour += 24
            now = datetime.datetime(utc_now.year, utc_now.month, utc_now.day, current_hour, utc_now.minute, utc_now.second, utc_now.microsecond)
            updated_order.update({
                'address': message_body, \
                'year': now.year, \
                'month': now.month, \
                'day': now.day, \
                'hour': now.hour, \
                'minute': now.minute})
            placed_order = datastore.Entity(client.key('Placed'))
            placed_order.update({
                'number': number, \
                'name': updated_order['name'], \
                'address': updated_order['address'], \
                'half_gallons': updated_order['half_gallons'], \
                'quarts': updated_order['quarts'], \
                'time': 'new' \
            })
            query = client.query(kind='Time')
            query.add_filter('slots', '>', 0)
            times = list(query.fetch())
            resp.message(list_times(updated_order, times))
            if len(times) == 0:
                return str(resp)
            client.put(updated_order)
            client.put(placed_order)
            placed = 'yes'
            session['placed'] = placed
        return str(resp)

    elif session.get('counter', 0) == 7:
        if message_body.lower() == "asap":
            resp.message(asap())
            return str(resp)
        converted_time = time_format(message_body)
        time_valid = valid_time(converted_time, client, mess_client)
        if converted_time == False:
            resp.message("Please enter a time in the correct format.\n\nExample:\n10:00am")
            counter -= 1
            session['counter'] = counter
            return str(resp)
        if time_valid == False:
            resp.message("Time format entered is correct but please enter a future time within the available timeslots.")
            counter -= 1
            session['counter'] = counter
            return str(resp)
        if time_valid == 'morning':
            decrement_slot('9:00am-12:00pm')
        elif time_valid == 'afternoon':
            decrement_slot('2:00pm-5:00pm')
        elif time_valid == 'evening':
            decrement_slot('7:00pm-9:00pm')
        query = client.query(kind='Placed')
        query.add_filter('number', '=', number)
        query.add_filter('time', '=', 'new')
        new_order = list(query.fetch())
        updated_order = new_order[0]
        utc_now = datetime.datetime.now(datetime.timezone.utc)
        current_hour = utc_now.hour - 6
        if current_hour < 0:
            current_hour += 24
        now = datetime.datetime(utc_now.year, utc_now.month, utc_now.day, current_hour, utc_now.minute, utc_now.second, utc_now.microsecond)
        updated_order.update({
            'time': message_body, \
            'time_ordered': str(now)})
        message = mess_client.messages.create(
            body='number: %s, name: %s, address: %s, time: %s, half gallons: %d, quarts: %d' % (number, updated_order['name'], \
                updated_order['address'], updated_order['time'], \
                int(updated_order['half_gallons']), int(updated_order['quarts'])),
            from_=cred.get_speedie_number(),
            to=cred.get_common_number()
        )
        print(message.sid)
        resp.message("Thank you for your order! We'll bring your coffee at %s. You will be contacted by the delivery team for updates.\n\nText COFFEE at any time to place another order.\n\nThank you for being a beta tester for our ordering software. If you feel like you have exhausted the capabilites of the software and have tested it thoroughly, we would really appreciate it if you would out the survey below to let us know how it worked for you. Thanks again!\nhttps://tulane.co1.qualtrics.com/jfe/form/SV_1Y3KPGKY2UYo3ul" % updated_order['time'])
        client.put(updated_order)
        placed = 'no'
        session['placed'] = placed
        customer = 'new'
        session['customer'] = customer
        counter = 0
        session['counter'] = counter
        return str(resp)

def time_format(message_body):
    i = 0
    while i < len(message_body):
        if (message_body[i] == ' ') and (i < len(message_body) - 1):
            message_body = message_body[:i] + message_body[(i + 1):]
            continue
        elif (message_body[i] == ' ') and (i == len(message_body) - 1):
            message_body = message_body[:i]
            break
        i += 1
    i = 0
    if message_body[1] == ':':
        message_body = '0' + message_body
    if message_body[2] == ':':
        message_body = message_body[:2] + message_body[3:]
    else:
        return False
    try:
        hours = int(message_body[:2])
    except ValueError:
        return False
    try:
        minutes = int(message_body[2:4])
    except ValueError:
        return False
    tod = message_body[4:]
    try:
        if (hours > 12) or (hours < 0):
            return False
    except TypeError:
        return False
    try:
        if (minutes > 59) or (minutes < 0):
            return False
    except TypeError:
        return False
    if (tod.lower() != 'am') and (tod.lower() != 'pm'):
        return False
    if (tod.lower() == 'pm') and (hours != 12):
        hours = hours + 12
    if (tod.lower() == 'am') and (hours == 12):
        hours = 0
    return datetime.time(hours, minutes)

def valid_time(time, client, mess_client):
    if time == False:
        return False
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    current_hour = utc_now.hour - 6
    if current_hour < 0:
        current_hour += 24
    now = datetime.datetime(utc_now.year, utc_now.month, utc_now.day, current_hour, utc_now.minute, utc_now.second, utc_now.microsecond)
    delivery_time = datetime.datetime(now.year, now.month, now.day, time.hour, time.minute)
    if delivery_time < now:
        return False
    query = client.query(kind='Time')
    query.add_filter('slots', '>', 0)
    times = list(query.fetch())
    for time in times:
        before_cutoff = datetime.datetime(now.year, now.month, now.day, int(time['start_hour']), 0)
        after_cutoff = datetime.datetime(now.year, now.month, now.day, int(time['end_hour']), 0)
        if (delivery_time <= after_cutoff) and (delivery_time >= before_cutoff):
            if int(time['start_hour']) == 9:
                return 'morning'
            elif int(time['start_hour']) == 14:
                return 'afternoon'
            elif int(time['start_hour']) == 19:
                return 'evening'
    return False

def reload():
    client = datastore.Client('speedie-bean-twilio')
    resp = MessagingResponse()
    query = client.query(kind='Time')
    time_slots = list(query.fetch())
    for i in range(len(time_slots)):
        time_slot = time_slots[i]
        time_slot.update({'slots': 10})
        client.put(time_slot)
    counter = session.get('counter', 0)
    counter -= 1
    session['counter'] = counter
    resp.message("Done")
    return str(resp)

def remove(time_period):
    client = datastore.Client('speedie-bean-twilio')
    resp = MessagingResponse()
    query = client.query(kind='Time')
    query.add_filter('time', '=', time_period)
    time_slots = list(query.fetch())
    time_slot = time_slots[0]
    time_slot.update({'slots': 0})
    client.put(time_slot)
    counter = session.get('counter', 0)
    counter -= 1
    session['counter'] = counter
    resp.message("Done")
    return str(resp)

def restart(number):
    client = datastore.Client('speedie-bean-twilio')
    counter = 1
    session['counter'] = counter
    query = client.query(kind='Placed')
    query.add_filter('number', '=', number)
    query.add_filter('time', '=', 'new')
    new_order = list(query.fetch())
    if len(new_order) != 0:
        for i in range(len(new_order)):
            updated_order = new_order[0]
            client.delete(updated_order.key)
    query = client.query(kind='Orders')
    query.add_filter('number', '=', number)
    query.add_filter('address', '=', '1000223')
    new_order = list(query.fetch())
    if len(new_order) != 0:
        for i in range(len(new_order)):
            updated_order = new_order[0]
            client.delete(updated_order.key)

def cancel_order(number):
    client = datastore.Client('speedie-bean-twilio')
    resp = MessagingResponse()
    counter = 0
    session['counter'] = counter
    query = client.query(kind='Placed')
    query.add_filter('number', '=', number)
    query.add_filter('time', '=', 'new')
    new_order = list(query.fetch())
    if len(new_order) != 0:
        for i in range(len(new_order)):
            updated_order = new_order[0]
            client.delete(updated_order.key)
    query = client.query(kind='Orders')
    query.add_filter('number', '=', number)
    query.add_filter('address', '=', '1000223')
    new_order = list(query.fetch())
    if len(new_order) != 0:
        for i in range(len(new_order)):
            updated_order = new_order[0]
            client.delete(updated_order.key)
    resp.message("Order cancelled.")
    return str(resp)

def list_times(order, times):
    resp = MessagingResponse()
    if len(times) == 3:
        string = "We will bring you %s Large coffee(s) and %s Small coffee(s) to %s. When should we bring it to you?\n\nAvailable time slots:\n9:00am-12:00pm\n2:00pm-5:00pm\n7:00pm-9:00pm\n\nPlease respond with ASAP to have the coffee delivered as soon as possible or enter a time within the available slots listed in the format shown in the following example:\n10:00am" % (order['half_gallons'], order['quarts'], order['address'])
    elif len(times) == 2:
        string = "We will bring you %s Large coffee(s) and %s Small coffee(s) to %s. When should we bring it to you?\n\nAvailable time slots:\n%s\n%s\n\nPlease respond with ASAP to have the coffee delivered as soon as possible or enter a time within the available slots listed in the format shown in the following example:\n10:00am" % (order['half_gallons'], order['quarts'], order['address'], times[0]['time'], times[1]['time'])
    elif len(times) == 1:
        string = "We will bring you %s Large coffee(s) and %s Small coffee(s) to %s. When should we bring it to you?\n\nAvailable time slots:\n%s\n\nPlease respond with ASAP to have the coffee delivered as soon as possible or enter a time within the available slots listed in the format shown in the following example:\n10:00am" % (order['half_gallons'], order['quarts'], order['address'], times[0]['time'])
    elif len(times) == 0:
        string = "We're sorry, there are no available delivery time slots, please try again later."
        query = client.query(kind='Placed')
        query.add_filter('number', '=', number)
        query.add_filter('time', '=', 'new')
        new_order = list(query.fetch())
        if len(new_order) != 0:
            for i in range(len(new_order)):
                updated_order = new_order[0]
                client.delete(updated_order.key)
        counter = 0
        session['counter'] = counter
        placed = 'no'
        session['placed'] = placed
    return string

def asap():
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    current_hour = utc_now.hour - 6
    if current_hour < 0:
        current_hour += 24
    now = datetime.datetime(utc_now.year, utc_now.month, utc_now.day, current_hour, utc_now.minute, utc_now.second, utc_now.microsecond)
    first = datetime.datetime(now.year, now.month, now.day, 12, 0)
    second = datetime.datetime(now.year, now.month, now.day, 17, 0)
    third = datetime.datetime(now.year, now.month, now.day, 21, 0)
    if now <= first:
        query = client.query(kind='Time')
        query.add_filter('time', '=', '9:00am-12:00pm')
        time_slots = list(query.fetch())
        time_slot = time_slots[0]
        if int(time_slot['slots']) != 0:
            previous_slots = int(time_slot['slots'])
            time_slot.update({'slots': previous_slots - 1})
            client.put(time_slot)
            string = "Thank you for your order! We'll bring your coffee as soon as possible. You will be contacted by the delivery team for updates.\nhttps://tulane.co1.qualtrics.com/jfe/form/SV_1Y3KPGKY2UYo3ul\n\nText COFFEE at any time to place another order."
            placed = 'no'
            session['placed'] = placed
            customer = 'new'
            session['customer'] = customer
            counter = 0
            session['counter'] = counter
    elif now <= second:
        query = client.query(kind='Time')
        query.add_filter('time', '=', '2:00pm-5:00pm')
        time_slots = list(query.fetch())
        time_slot = time_slots[0]
        if int(time_slot['slots']) != 0:
            previous_slots = int(time_slot['slots'])
            time_slot.update({'slots': previous_slots - 1})
            client.put(time_slot)
            string = "Thank you for your order! We'll bring your coffee as soon as possible. You will be contacted by the delivery team for updates.\n\nText COFFEE at any time to place another order.\n\nThank you for being a beta tester for our ordering software. If you feel like you have exhausted the capabilites of the software and have tested it thoroughly, we would really appreciate it if you would out the survey below to let us know how it worked for you. Thanks again!\nhttps://tulane.co1.qualtrics.com/jfe/form/SV_1Y3KPGKY2UYo3ul"
            placed = 'no'
            session['placed'] = placed
            customer = 'new'
            session['customer'] = customer
            counter = 0
            session['counter'] = counter
    elif now <= third:
        query = client.query(kind='Time')
        query.add_filter('time', '=', '7:00pm-9:00pm')
        time_slots = list(query.fetch())
        time_slot = time_slots[0]
        if int(time_slot['slots']) != 0:
            previous_slots = int(time_slot['slots'])
            time_slot.update({'slots': previous_slots - 1})
            client.put(time_slot)
            string = "Thank you for your order! We'll bring your coffee as soon as possible. You will be contacted by the delivery team for updates.\n\nText COFFEE at any time to place another order.\n\nThank you for being a beta tester for our ordering software. If you feel like you have exhausted the capabilites of the software and have tested it thoroughly, we would really appreciate it if you would out the survey below to let us know how it worked for you. Thanks again!\nhttps://tulane.co1.qualtrics.com/jfe/form/SV_1Y3KPGKY2UYo3ul"
            placed = 'no'
            session['placed'] = placed
            customer = 'new'
            session['customer'] = customer
            counter = 0
            session['counter'] = counter
    else:
        string = "We're sorry, there are no available delivery time slots, please try again later."
        query = client.query(kind='Placed')
        query.add_filter('number', '=', number)
        query.add_filter('time', '=', 'new')
        new_order = list(query.fetch())
        if len(new_order) != 0:
            for i in range(len(new_order)):
                updated_order = new_order[0]
                client.delete(updated_order.key)
        counter = 0
        session['counter'] = counter
        placed = 'no'
        session['placed'] = placed
    return string

def decrement_slot(time_period):
    client = datastore.Client('speedie-bean-twilio')
    query = client.query(kind='Time')
    query.add_filter('time', '=', time_period)
    time_slots = list(query.fetch())
    time_slot = time_slots[0]
    previous = int(time_slot['slots'])
    time_slot.update({'slots': previous - 1})
    client.put(time_slot)

if __name__ == "__main__":
    app.run(debug=True)