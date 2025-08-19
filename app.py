import os
import logging
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash
from collections import defaultdict

# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "zen-food-tracker-secret-key")

# In-memory data storage
users = {}  # {user_id: {'name': str, 'role': str}}
menu_items = {}  # {item_id: {'name': str, 'price': float, 'stall_owner': str}}
sales = []  # [{'item_id': int, 'quantity': int, 'total': float, 'timestamp': datetime, 'stall_owner': str}]
purchases = []  # [{'user_id': str, 'item_id': int, 'item_name': str, 'stall_name': str, 'price': float, 'timestamp': datetime}]

# Auto-incrementing IDs
next_user_id = 1
next_item_id = 1

@app.route('/')
def index():
    if 'user_id' in session:
        user = users.get(session['user_id'])
        if user:
            if user['role'] == 'student':
                return redirect(url_for('student_dashboard'))
            else:
                return redirect(url_for('stall_dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        role = request.form.get('role')
        
        if not name or role not in ['student', 'stall_owner']:
            flash('Please enter a valid name and select a role', 'error')
            return render_template('login.html')
        
        # Check if user exists
        user_id = None
        for uid, user in users.items():
            if user['name'].lower() == name.lower() and user['role'] == role:
                user_id = uid
                break
        
        # Create new user if doesn't exist
        if not user_id:
            global next_user_id
            user_id = str(next_user_id)
            users[user_id] = {'name': name, 'role': role}
            next_user_id += 1
            flash(f'Welcome to Zen School Food Tracker, {name}!', 'success')
        else:
            flash(f'Welcome back, {name}!', 'success')
        
        session['user_id'] = user_id
        
        if role == 'student':
            return redirect(url_for('student_dashboard'))
        else:
            return redirect(url_for('stall_dashboard'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))

@app.route('/student/dashboard')
def student_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = users.get(session['user_id'])
    if not user or user['role'] != 'student':
        return redirect(url_for('login'))
    
    # Calculate spending statistics
    user_purchases = [p for p in purchases if p['user_id'] == session['user_id']]
    
    # Today's spending
    today = datetime.now().date()
    today_purchases = [p for p in user_purchases if p['timestamp'].date() == today]
    today_spend = sum(p.get('total_price', p['price']) for p in today_purchases)
    
    # Weekly spending
    week_ago = datetime.now() - timedelta(days=7)
    week_purchases = [p for p in user_purchases if p['timestamp'] >= week_ago]
    weekly_spend = sum(p.get('total_price', p['price']) for p in week_purchases)
    
    # Recent purchases (last 10)
    recent_purchases = sorted(user_purchases, key=lambda x: x['timestamp'], reverse=True)[:10]
    
    return render_template('student_dashboard.html', 
                         user=user,
                         today_spend=today_spend,
                         weekly_spend=weekly_spend,
                         today_items=len(today_purchases),
                         recent_purchases=recent_purchases)

@app.route('/stall/dashboard')
def stall_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = users.get(session['user_id'])
    if not user or user['role'] != 'stall_owner':
        return redirect(url_for('login'))
    
    # Calculate sales statistics for this stall owner
    stall_sales = [s for s in sales if s['stall_owner'] == user['name']]
    
    total_sales = sum(s['quantity'] for s in stall_sales)
    total_revenue = sum(s['total'] for s in stall_sales)
    
    # Recent sales (last 10)
    recent_sales = sorted(stall_sales, key=lambda x: x['timestamp'], reverse=True)[:10]
    
    # Get menu items for this stall
    stall_menu = {k: v for k, v in menu_items.items() if v['stall_owner'] == user['name']}
    
    return render_template('stall_dashboard.html',
                         user=user,
                         total_sales=total_sales,
                         total_revenue=total_revenue,
                         recent_sales=recent_sales,
                         menu_items=stall_menu)

@app.route('/browse-menu')
def browse_menu():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = users.get(session['user_id'])
    if not user or user['role'] != 'student':
        return redirect(url_for('login'))
    
    # Group menu items by stall owner
    stalls = defaultdict(list)
    for item_id, item in menu_items.items():
        stalls[item['stall_owner']].append({
            'id': item_id,
            'name': item['name'],
            'price': item['price']
        })
    
    return render_template('browse_menu.html', user=user, stalls=dict(stalls))

@app.route('/add-menu-item', methods=['GET', 'POST'])
def add_menu_item():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = users.get(session['user_id'])
    if not user or user['role'] != 'stall_owner':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        price_str = request.form.get('price', '').strip()
        
        if not name or not price_str:
            flash('Please fill in all fields', 'error')
            return render_template('add_menu_item.html', user=user)
        
        try:
            price = float(price_str)
            if price <= 0:
                raise ValueError()
        except ValueError:
            flash('Please enter a valid price', 'error')
            return render_template('add_menu_item.html', user=user)
        
        global next_item_id
        menu_items[str(next_item_id)] = {
            'name': name,
            'price': price,
            'stall_owner': user['name']
        }
        next_item_id += 1
        
        flash(f'Added {name} to your menu!', 'success')
        return redirect(url_for('stall_dashboard'))
    
    return render_template('add_menu_item.html', user=user)

@app.route('/record-sale')
def record_sale():
    # Redirect to stall dashboard since manual sales recording is disabled
    flash('Sales are now recorded automatically when students make purchases!', 'info')
    return redirect(url_for('stall_dashboard'))

@app.route('/log-purchase', methods=['POST'])
def log_purchase():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = users.get(session['user_id'])
    if not user or user['role'] != 'student':
        return redirect(url_for('login'))
    
    item_id = request.form.get('item_id')
    quantity_str = request.form.get('quantity', '1').strip()
    
    if not item_id or item_id not in menu_items:
        flash('Invalid item selected', 'error')
        return redirect(url_for('browse_menu'))
    
    try:
        quantity = int(quantity_str)
        if quantity <= 0 or quantity > 99:
            raise ValueError()
    except ValueError:
        flash('Please enter a valid quantity (1-99)', 'error')
        return redirect(url_for('browse_menu'))
    
    item = menu_items[item_id]
    total_price = item['price'] * quantity
    
    # Log the purchase for the student
    purchases.append({
        'user_id': session['user_id'],
        'item_id': item_id,
        'item_name': item['name'],
        'stall_name': item['stall_owner'],
        'price': item['price'],
        'quantity': quantity,
        'total_price': total_price,
        'timestamp': datetime.now()
    })
    
    # Automatically record the sale for the stall owner
    sales.append({
        'item_id': item_id,
        'item_name': item['name'],
        'quantity': quantity,
        'total': total_price,
        'timestamp': datetime.now(),
        'stall_owner': item['stall_owner'],
        'buyer_name': user['name']
    })
    
    if quantity == 1:
        flash(f'Purchased {item["name"]} for ₹{total_price:.2f}!', 'success')
    else:
        flash(f'Purchased {quantity}x {item["name"]} for ₹{total_price:.2f}!', 'success')
    
    return redirect(url_for('browse_menu'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
