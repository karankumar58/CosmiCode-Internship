from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import csv
from io import StringIO
from functools import wraps
import re
from sqlalchemy import or_

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

from models import db, User, Product, Supplier, Transaction, create_default_admin, get_inventory_stats

# Initialize database with app
db.init_app(app)

# Create database tables and default admin
with app.app_context():
    db.create_all()
    create_default_admin()

def login_required(f):
    """Decorator to require login for protected routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin role for protected routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        
        user = User.query.get(session['user_id'])
        if not user or not user.is_admin():
            flash('Admin access required.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    """Get current logged-in user"""
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    return None

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password):
    """Validate password strength"""
    if len(password) < 6:
        return False, "Password must be at least 6 characters long"
    if not re.search(r'[A-Za-z]', password):
        return False, "Password must contain at least one letter"
    return True, "Password is valid"

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET'])
def login():
    # Redirect if already logged in
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login_post():
    """Handle login form submission"""
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    
    # Validate input
    if not username or not password:
        flash('Please enter both username and password.', 'error')
        return redirect(url_for('login'))
    
    # Find user
    user = User.query.filter_by(username=username).first()
    
    if user and user.check_password(password) and user.is_active:
        # Successful login
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role
        
        # Update last login
        user.update_last_login()
        
        flash(f'Welcome back, {user.username}!', 'success')
        
        # Redirect to next page or dashboard
        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
        return redirect(url_for('dashboard'))
    else:
        flash('Invalid username or password.', 'error')
        return redirect(url_for('login'))

@app.route('/register', methods=['GET'])
def register():
    # Redirect if already logged in
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/register', methods=['POST'])
def register_post():
    """Handle registration form submission"""
    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    confirm_password = request.form.get('confirm_password', '')
    
    # Validate input
    if not all([username, email, password, confirm_password]):
        flash('Please fill in all fields.', 'error')
        return redirect(url_for('register'))
    
    # Validate username
    if len(username) < 3:
        flash('Username must be at least 3 characters long.', 'error')
        return redirect(url_for('register'))
    
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        flash('Username can only contain letters, numbers, and underscores.', 'error')
        return redirect(url_for('register'))
    
    # Validate email
    if not validate_email(email):
        flash('Please enter a valid email address.', 'error')
        return redirect(url_for('register'))
    
    # Validate password
    is_valid, message = validate_password(password)
    if not is_valid:
        flash(message, 'error')
        return redirect(url_for('register'))
    
    # Check password confirmation
    if password != confirm_password:
        flash('Passwords do not match.', 'error')
        return redirect(url_for('register'))
    
    # Check if username or email already exists
    existing_user = User.query.filter(
        (User.username == username) | (User.email == email)
    ).first()
    
    if existing_user:
        if existing_user.username == username:
            flash('Username already exists. Please choose a different one.', 'error')
        else:
            flash('Email already registered. Please use a different email.', 'error')
        return redirect(url_for('register'))
    
    # Create new user
    try:
        new_user = User(
            username=username,
            email=email,
            role='staff'  # Default role
        )
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
        
    except Exception as e:
        db.session.rollback()
        flash('Registration failed. Please try again.', 'error')
        return redirect(url_for('register'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard with inventory overview"""
    user = get_current_user()
    stats = get_inventory_stats()
    
    # Get recent transactions
    recent_transactions = Transaction.query.order_by(
        Transaction.created_at.desc()
    ).limit(5).all()
    
    # Get low stock products
    from models import get_low_stock_products, get_out_of_stock_products
    low_stock_products = get_low_stock_products()
    out_of_stock_products = get_out_of_stock_products()
    
    return render_template('dashboard.html', 
                         user=user,
                         stats=stats,
                         recent_transactions=recent_transactions,
                         low_stock_products=low_stock_products,
                         out_of_stock_products=out_of_stock_products)

@app.route('/products')
@login_required
def products():
    """Display products with search and pagination"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str)
    category = request.args.get('category', '', type=str)
    supplier_id = request.args.get('supplier', '', type=int)
    stock_status = request.args.get('stock_status', '', type=str)
    
    # Build query
    query = Product.query.filter_by(is_active=True)
    
    # Apply search filter
    if search:
        query = query.filter(
            or_(
                Product.name.contains(search),
                Product.sku.contains(search),
                Product.description.contains(search)
            )
        )
    
    # Apply category filter
    if category:
        query = query.filter(Product.category == category)
    
    # Apply supplier filter
    if supplier_id:
        query = query.filter(Product.supplier_id == supplier_id)
    
    # Apply stock status filter
    if stock_status == 'low_stock':
        query = query.filter(Product.quantity <= Product.min_stock_level)
    elif stock_status == 'out_of_stock':
        query = query.filter(Product.quantity <= 0)
    elif stock_status == 'in_stock':
        query = query.filter(Product.quantity > Product.min_stock_level)
    
    # Paginate results
    products = query.order_by(Product.name).paginate(
        page=page, per_page=10, error_out=False
    )
    
    # Get filter options
    categories = db.session.query(Product.category).filter_by(is_active=True).distinct().all()
    categories = [cat[0] for cat in categories]
    
    suppliers = Supplier.query.filter_by(is_active=True).all()
    
    return render_template('products.html', 
                         products=products,
                         categories=categories,
                         suppliers=suppliers,
                         search=search,
                         selected_category=category,
                         selected_supplier=supplier_id,
                         selected_stock_status=stock_status)

@app.route('/products/add', methods=['GET', 'POST'])
@login_required
def add_product():
    """Add new product"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category = request.form.get('category', '').strip()
        description = request.form.get('description', '').strip()
        price = request.form.get('price', type=float)
        quantity = request.form.get('quantity', type=int)
        min_stock_level = request.form.get('min_stock_level', type=int)
        sku = request.form.get('sku', '').strip()
        supplier_id = request.form.get('supplier_id', type=int)
        
        # Validate input
        if not all([name, category, price is not None, quantity is not None, supplier_id]):
            flash('Please fill in all required fields.', 'error')
            return redirect(url_for('add_product'))
        
        if price < 0:
            flash('Price cannot be negative.', 'error')
            return redirect(url_for('add_product'))
        
        if quantity < 0:
            flash('Quantity cannot be negative.', 'error')
            return redirect(url_for('add_product'))
        
        # Check if SKU already exists
        if sku and Product.query.filter_by(sku=sku).first():
            flash('SKU already exists. Please use a different SKU.', 'error')
            return redirect(url_for('add_product'))
        
        # Create new product
        try:
            new_product = Product(
                name=name,
                category=category,
                description=description,
                price=price,
                quantity=quantity,
                min_stock_level=min_stock_level or 10,
                sku=sku or None,
                supplier_id=supplier_id
            )
            
            db.session.add(new_product)
            db.session.commit()
            
            flash(f'Product "{name}" added successfully!', 'success')
            return redirect(url_for('products'))
            
        except Exception as e:
            db.session.rollback()
            flash('Failed to add product. Please try again.', 'error')
            return redirect(url_for('add_product'))
    
    # GET request - show form
    suppliers = Supplier.query.filter_by(is_active=True).all()
    return render_template('add_product.html', suppliers=suppliers)

@app.route('/products/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    """Edit existing product"""
    product = Product.query.get_or_404(product_id)
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category = request.form.get('category', '').strip()
        description = request.form.get('description', '').strip()
        price = request.form.get('price', type=float)
        quantity = request.form.get('quantity', type=int)
        min_stock_level = request.form.get('min_stock_level', type=int)
        sku = request.form.get('sku', '').strip()
        supplier_id = request.form.get('supplier_id', type=int)
        
        # Validate input
        if not all([name, category, price is not None, quantity is not None, supplier_id]):
            flash('Please fill in all required fields.', 'error')
            return redirect(url_for('edit_product', product_id=product_id))
        
        if price < 0:
            flash('Price cannot be negative.', 'error')
            return redirect(url_for('edit_product', product_id=product_id))
        
        if quantity < 0:
            flash('Quantity cannot be negative.', 'error')
            return redirect(url_for('edit_product', product_id=product_id))
        
        # Check if SKU already exists (excluding current product)
        if sku:
            existing_sku = Product.query.filter(Product.sku == sku, Product.id != product_id).first()
            if existing_sku:
                flash('SKU already exists. Please use a different SKU.', 'error')
                return redirect(url_for('edit_product', product_id=product_id))
        
        # Update product
        try:
            product.name = name
            product.category = category
            product.description = description
            product.price = price
            product.quantity = quantity
            product.min_stock_level = min_stock_level or 10
            product.sku = sku or None
            product.supplier_id = supplier_id
            product.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            flash(f'Product "{name}" updated successfully!', 'success')
            return redirect(url_for('products'))
            
        except Exception as e:
            db.session.rollback()
            flash('Failed to update product. Please try again.', 'error')
            return redirect(url_for('edit_product', product_id=product_id))
    
    # GET request - show form
    suppliers = Supplier.query.filter_by(is_active=True).all()
    return render_template('edit_product.html', product=product, suppliers=suppliers)

@app.route('/products/delete/<int:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    """Delete product (soft delete)"""
    product = Product.query.get_or_404(product_id)
    
    try:
        # Soft delete - mark as inactive
        product.is_active = False
        product.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        flash(f'Product "{product.name}" deleted successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('Failed to delete product. Please try again.', 'error')
    
    return redirect(url_for('products'))

@app.route('/products/view/<int:product_id>')
@login_required
def view_product(product_id):
    """View product details"""
    product = Product.query.get_or_404(product_id)
    
    # Get recent transactions for this product
    recent_transactions = Transaction.query.filter_by(product_id=product_id)\
        .order_by(Transaction.created_at.desc()).limit(10).all()
    
    return render_template('view_product.html', 
                         product=product, 
                         recent_transactions=recent_transactions)

@app.route('/api/products/search')
@login_required
def api_product_search():
    """API endpoint for product search (for AJAX)"""
    query = request.args.get('q', '')
    
    if len(query) < 2:
        return jsonify([])
    
    products = Product.query.filter(
        Product.is_active == True,
        or_(
            Product.name.contains(query),
            Product.sku.contains(query)
        )
    ).limit(10).all()
    
    results = []
    for product in products:
        results.append({
            'id': product.id,
            'name': product.name,
            'sku': product.sku,
            'price': product.price,
            'quantity': product.quantity,
            'category': product.category
        })
    
    return jsonify(results)

@app.route('/suppliers')
@login_required
def suppliers():
    """Display suppliers with search and pagination"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str)
    
    # Build query
    query = Supplier.query.filter_by(is_active=True)
    
    # Apply search filter
    if search:
        query = query.filter(
            or_(
                Supplier.name.contains(search),
                Supplier.email.contains(search),
                Supplier.contact.contains(search)
            )
        )
    
    # Paginate results
    suppliers = query.order_by(Supplier.name).paginate(
        page=page, per_page=10, error_out=False
    )
    
    return render_template('suppliers.html', 
                         suppliers=suppliers,
                         search=search)

@app.route('/suppliers/add', methods=['GET', 'POST'])
@login_required
def add_supplier():
    """Add new supplier"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        contact = request.form.get('contact', '').strip()
        email = request.form.get('email', '').strip().lower()
        address = request.form.get('address', '').strip()
        
        # Validate input
        if not name:
            flash('Please provide a supplier name.', 'error')
            return redirect(url_for('add_supplier'))
        
        # Validate email if provided
        if email and not validate_email(email):
            flash('Please enter a valid email address.', 'error')
            return redirect(url_for('add_supplier'))
        
        # Check if supplier name already exists
        existing_supplier = Supplier.query.filter_by(name=name, is_active=True).first()
        if existing_supplier:
            flash('A supplier with this name already exists.', 'error')
            return redirect(url_for('add_supplier'))
        
        # Check if email already exists
        if email:
            existing_email = Supplier.query.filter_by(email=email, is_active=True).first()
            if existing_email:
                flash('A supplier with this email already exists.', 'error')
                return redirect(url_for('add_supplier'))
        
        # Create new supplier
        try:
            new_supplier = Supplier(
                name=name,
                contact=contact or None,
                email=email or None,
                address=address or None
            )
            
            db.session.add(new_supplier)
            db.session.commit()
            
            flash(f'Supplier "{name}" added successfully!', 'success')
            return redirect(url_for('suppliers'))
            
        except Exception as e:
            db.session.rollback()
            flash('Failed to add supplier. Please try again.', 'error')
            return redirect(url_for('add_supplier'))
    
    # GET request - show form
    return render_template('add_supplier.html')

@app.route('/suppliers/edit/<int:supplier_id>', methods=['GET', 'POST'])
@login_required
def edit_supplier(supplier_id):
    """Edit existing supplier"""
    supplier = Supplier.query.get_or_404(supplier_id)
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        contact = request.form.get('contact', '').strip()
        email = request.form.get('email', '').strip().lower()
        address = request.form.get('address', '').strip()
        
        # Validate input
        if not name:
            flash('Please provide a supplier name.', 'error')
            return redirect(url_for('edit_supplier', supplier_id=supplier_id))
        
        # Validate email if provided
        if email and not validate_email(email):
            flash('Please enter a valid email address.', 'error')
            return redirect(url_for('edit_supplier', supplier_id=supplier_id))
        
        # Check if supplier name already exists (excluding current supplier)
        existing_supplier = Supplier.query.filter(
            Supplier.name == name, 
            Supplier.id != supplier_id,
            Supplier.is_active == True
        ).first()
        if existing_supplier:
            flash('A supplier with this name already exists.', 'error')
            return redirect(url_for('edit_supplier', supplier_id=supplier_id))
        
        # Check if email already exists (excluding current supplier)
        if email:
            existing_email = Supplier.query.filter(
                Supplier.email == email,
                Supplier.id != supplier_id,
                Supplier.is_active == True
            ).first()
            if existing_email:
                flash('A supplier with this email already exists.', 'error')
                return redirect(url_for('edit_supplier', supplier_id=supplier_id))
        
        # Update supplier
        try:
            supplier.name = name
            supplier.contact = contact or None
            supplier.email = email or None
            supplier.address = address or None
            supplier.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            flash(f'Supplier "{name}" updated successfully!', 'success')
            return redirect(url_for('suppliers'))
            
        except Exception as e:
            db.session.rollback()
            flash('Failed to update supplier. Please try again.', 'error')
            return redirect(url_for('edit_supplier', supplier_id=supplier_id))
    
    # GET request - show form
    return render_template('edit_supplier.html', supplier=supplier)

@app.route('/suppliers/delete/<int:supplier_id>', methods=['POST'])
@login_required
def delete_supplier(supplier_id):
    """Delete supplier (soft delete)"""
    supplier = Supplier.query.get_or_404(supplier_id)
    
    # Check if supplier has active products
    active_products = Product.query.filter_by(supplier_id=supplier_id, is_active=True).count()
    if active_products > 0:
        flash(f'Cannot delete supplier "{supplier.name}" because it has {active_products} active products. Please reassign or delete the products first.', 'error')
        return redirect(url_for('suppliers'))
    
    try:
        # Soft delete - mark as inactive
        supplier.is_active = False
        supplier.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        flash(f'Supplier "{supplier.name}" deleted successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('Failed to delete supplier. Please try again.', 'error')
    
    return redirect(url_for('suppliers'))

@app.route('/suppliers/view/<int:supplier_id>')
@login_required
def view_supplier(supplier_id):
    """View supplier details"""
    supplier = Supplier.query.get_or_404(supplier_id)
    
    # Get products from this supplier
    products = Product.query.filter_by(supplier_id=supplier_id, is_active=True)\
        .order_by(Product.name).all()
    
    # Calculate supplier statistics
    total_products = len(products)
    total_stock_value = sum(p.get_total_value() for p in products)
    low_stock_products = [p for p in products if p.is_low_stock()]
    out_of_stock_products = [p for p in products if p.is_out_of_stock()]
    
    supplier_stats = {
        'total_products': total_products,
        'total_stock_value': total_stock_value,
        'low_stock_count': len(low_stock_products),
        'out_of_stock_count': len(out_of_stock_products)
    }
    
    return render_template('view_supplier.html', 
                         supplier=supplier,
                         products=products,
                         supplier_stats=supplier_stats)

@app.route('/api/suppliers/search')
@login_required
def api_supplier_search():
    """API endpoint for supplier search (for AJAX)"""
    query = request.args.get('q', '')
    
    if len(query) < 2:
        return jsonify([])
    
    suppliers = Supplier.query.filter(
        Supplier.is_active == True,
        or_(
            Supplier.name.contains(query),
            Supplier.email.contains(query)
        )
    ).limit(10).all()
    
    results = []
    for supplier in suppliers:
        results.append({
            'id': supplier.id,
            'name': supplier.name,
            'email': supplier.email,
            'contact': supplier.contact,
            'total_products': supplier.get_total_products()
        })
    
    return jsonify(results)

@app.route('/transactions')
@login_required
def transactions():
    """Display transactions with search and pagination"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str)
    transaction_type = request.args.get('type', '', type=str)
    product_id = request.args.get('product_id', '', type=int)
    user_id = request.args.get('user_id', '', type=int)
    date_from = request.args.get('date_from', '', type=str)
    date_to = request.args.get('date_to', '', type=str)
    
    # Build query
    query = Transaction.query
    
    # Apply search filter
    if search:
        query = query.join(Product).filter(
            or_(
                Product.name.contains(search),
                Product.sku.contains(search),
                Transaction.notes.contains(search)
            )
        )
    
    # Apply transaction type filter
    if transaction_type:
        query = query.filter(Transaction.transaction_type == transaction_type)
    
    # Apply product filter
    if product_id:
        query = query.filter(Transaction.product_id == product_id)
    
    # Apply user filter
    if user_id:
        query = query.filter(Transaction.user_id == user_id)
    
    # Apply date filters
    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(Transaction.created_at >= from_date)
        except ValueError:
            pass
    
    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d')
            # Add one day to include the entire end date
            to_date = to_date.replace(hour=23, minute=59, second=59)
            query = query.filter(Transaction.created_at <= to_date)
        except ValueError:
            pass
    
    # Paginate results
    transactions = query.order_by(Transaction.created_at.desc()).paginate(
        page=page, per_page=15, error_out=False
    )
    
    # Get filter options
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    users = User.query.filter_by(is_active=True).order_by(User.username).all()
    
    return render_template('transactions.html', 
                         transactions=transactions,
                         products=products,
                         users=users,
                         search=search,
                         selected_type=transaction_type,
                         selected_product=product_id,
                         selected_user=user_id,
                         date_from=date_from,
                         date_to=date_to)

@app.route('/transactions/add', methods=['GET', 'POST'])
@login_required
def add_transaction():
    """Add new transaction (stock in/out)"""
    if request.method == 'POST':
        product_id = request.form.get('product_id', type=int)
        transaction_type = request.form.get('transaction_type', '').strip()
        quantity = request.form.get('quantity', type=int)
        notes = request.form.get('notes', '').strip()
        
        # Validate input
        if not all([product_id, transaction_type, quantity]):
            flash('Please fill in all required fields.', 'error')
            return redirect(url_for('add_transaction'))
        
        if transaction_type not in ['add', 'remove']:
            flash('Invalid transaction type.', 'error')
            return redirect(url_for('add_transaction'))
        
        if quantity <= 0:
            flash('Quantity must be greater than zero.', 'error')
            return redirect(url_for('add_transaction'))
        
        # Get product
        product = Product.query.get(product_id)
        if not product or not product.is_active:
            flash('Invalid product selected.', 'error')
            return redirect(url_for('add_transaction'))
        
        # Check if removing more stock than available
        if transaction_type == 'remove' and product.quantity < quantity:
            flash(f'Cannot remove {quantity} units. Only {product.quantity} units available.', 'error')
            return redirect(url_for('add_transaction'))
        
        # Create transaction and update stock
        try:
            transaction = product.update_stock(
                quantity_change=quantity,
                transaction_type=transaction_type,
                user_id=session['user_id'],
                notes=notes or None
            )
            
            # Set unit price for the transaction
            transaction.unit_price = product.price
            db.session.commit()
            
            action_word = 'added to' if transaction_type == 'add' else 'removed from'
            flash(f'Successfully {action_word} {product.name}: {quantity} units', 'success')
            return redirect(url_for('transactions'))
            
        except ValueError as e:
            flash(str(e), 'error')
            return redirect(url_for('add_transaction'))
        except Exception as e:
            db.session.rollback()
            flash('Failed to record transaction. Please try again.', 'error')
            return redirect(url_for('add_transaction'))
    
    # GET request - show form
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    
    # Pre-select product if provided in URL
    selected_product_id = request.args.get('product_id', type=int)
    selected_type = request.args.get('type', '')
    
    return render_template('add_transaction.html', 
                         products=products,
                         selected_product_id=selected_product_id,
                         selected_type=selected_type)

@app.route('/api/transactions/product-info/<int:product_id>')
@login_required
def api_product_info(product_id):
    """API endpoint to get product info for transaction form"""
    product = Product.query.get_or_404(product_id)
    
    return jsonify({
        'id': product.id,
        'name': product.name,
        'sku': product.sku,
        'current_stock': product.quantity,
        'price': product.price,
        'category': product.category,
        'supplier': product.supplier.name,
        'is_low_stock': product.is_low_stock(),
        'is_out_of_stock': product.is_out_of_stock()
    })

@app.route('/reports')
@login_required
def reports():
    """Reports dashboard"""
    # Get date range from query params
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    # Default to last 30 days if no dates provided
    if not date_from or not date_to:
        from datetime import timedelta
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        date_from = start_date.strftime('%Y-%m-%d')
        date_to = end_date.strftime('%Y-%m-%d')
    
    try:
        start_date = datetime.strptime(date_from, '%Y-%m-%d')
        end_date = datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
    except ValueError:
        flash('Invalid date format. Using last 30 days.', 'warning')
        from datetime import timedelta
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        date_from = start_date.strftime('%Y-%m-%d')
        date_to = end_date.strftime('%Y-%m-%d')
    
    # Get inventory statistics
    stats = get_inventory_stats()
    
    # Get transactions in date range
    transactions_in_range = Transaction.query.filter(
        Transaction.created_at >= start_date,
        Transaction.created_at <= end_date
    ).all()
    
    # Calculate transaction statistics
    stock_in_count = len([t for t in transactions_in_range if t.transaction_type == 'add'])
    stock_out_count = len([t for t in transactions_in_range if t.transaction_type == 'remove'])
    stock_in_quantity = sum(t.quantity for t in transactions_in_range if t.transaction_type == 'add')
    stock_out_quantity = sum(t.quantity for t in transactions_in_range if t.transaction_type == 'remove')
    
    # Get low stock and out of stock products
    from models import get_low_stock_products, get_out_of_stock_products
    low_stock_products = get_low_stock_products()
    out_of_stock_products = get_out_of_stock_products()
    
    # Get top products by transaction volume
    from sqlalchemy import func
    top_products = db.session.query(
        Product.name,
        func.sum(Transaction.quantity).label('total_quantity'),
        func.count(Transaction.id).label('transaction_count')
    ).join(Transaction).filter(
        Transaction.created_at >= start_date,
        Transaction.created_at <= end_date
    ).group_by(Product.id).order_by(func.sum(Transaction.quantity).desc()).limit(10).all()
    
    # Get category breakdown
    category_stats = db.session.query(
        Product.category,
        func.count(Product.id).label('product_count'),
        func.sum(Product.quantity * Product.price).label('total_value')
    ).filter(Product.is_active == True).group_by(Product.category).all()
    
    report_data = {
        'date_range': {
            'from': date_from,
            'to': date_to,
            'days': (end_date - start_date).days + 1
        },
        'inventory_stats': stats,
        'transaction_stats': {
            'stock_in_count': stock_in_count,
            'stock_out_count': stock_out_count,
            'stock_in_quantity': stock_in_quantity,
            'stock_out_quantity': stock_out_quantity,
            'total_transactions': len(transactions_in_range)
        },
        'alerts': {
            'low_stock_products': low_stock_products,
            'out_of_stock_products': out_of_stock_products
        },
        'top_products': top_products,
        'category_stats': category_stats
    }
    
    return render_template('reports.html', 
                         report_data=report_data,
                         date_from=date_from,
                         date_to=date_to)

@app.route('/reports/export')
@login_required
def export_report():
    """Export reports as CSV"""
    report_type = request.args.get('type', 'inventory')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    # Set default date range if not provided
    if not date_from or not date_to:
        from datetime import timedelta
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        date_from = start_date.strftime('%Y-%m-%d')
        date_to = end_date.strftime('%Y-%m-%d')
    
    try:
        start_date = datetime.strptime(date_from, '%Y-%m-%d')
        end_date = datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
    except ValueError:
        flash('Invalid date format.', 'error')
        return redirect(url_for('reports'))
    
    from flask import Response
    
    if report_type == 'inventory':
        # Export current inventory
        products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Product Name', 'SKU', 'Category', 'Supplier', 'Price', 'Current Stock', 'Min Stock Level', 'Stock Status', 'Total Value'])
        
        # Write data
        for product in products:
            writer.writerow([
                product.name,
                product.sku or '',
                product.category,
                product.supplier.name,
                product.price,
                product.quantity,
                product.min_stock_level,
                product.get_stock_status(),
                product.get_total_value()
            ])
        
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename=inventory_report_{date_from}_to_{date_to}.csv'}
        )
    
    elif report_type == 'transactions':
        # Export transactions in date range
        transactions = Transaction.query.filter(
            Transaction.created_at >= start_date,
            Transaction.created_at <= end_date
        ).order_by(Transaction.created_at.desc()).all()
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Date', 'Product', 'SKU', 'Type', 'Quantity', 'Old Stock', 'New Stock', 'User', 'Notes'])
        
        # Write data
        for transaction in transactions:
            writer.writerow([
                transaction.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                transaction.product.name,
                transaction.product.sku or '',
                'Stock In' if transaction.transaction_type == 'add' else 'Stock Out',
                transaction.quantity,
                transaction.old_quantity,
                transaction.new_quantity,
                transaction.user.username,
                transaction.notes or ''
            ])
        
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename=transactions_report_{date_from}_to_{date_to}.csv'}
        )
    
    elif report_type == 'low_stock':
        # Export low stock report
        from models import get_low_stock_products, get_out_of_stock_products
        low_stock = get_low_stock_products()
        out_of_stock = get_out_of_stock_products()
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Product Name', 'SKU', 'Category', 'Supplier', 'Current Stock', 'Min Stock Level', 'Status'])
        
        # Write out of stock products first
        for product in out_of_stock:
            writer.writerow([
                product.name,
                product.sku or '',
                product.category,
                product.supplier.name,
                product.quantity,
                product.min_stock_level,
                'Out of Stock'
            ])
        
        # Write low stock products
        for product in low_stock:
            if not product.is_out_of_stock():  # Don't duplicate out of stock items
                writer.writerow([
                    product.name,
                    product.sku or '',
                    product.category,
                    product.supplier.name,
                    product.quantity,
                    product.min_stock_level,
                    'Low Stock'
                ])
        
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename=low_stock_report_{datetime.now().strftime("%Y%m%d")}.csv'}
        )
    
    else:
        flash('Invalid report type.', 'error')
        return redirect(url_for('reports'))

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/logout')
def logout():
    """Handle user logout"""
    username = session.get('username', 'User')
    session.clear()
    flash(f'Goodbye, {username}! You have been logged out successfully.', 'success')
    return redirect(url_for('login'))

@app.route('/profile')
@login_required
def profile():
    """User profile page"""
    user = get_current_user()
    return render_template('profile.html', user=user)

@app.route('/change-password', methods=['POST'])
@login_required
def change_password():
    """Handle password change"""
    user = get_current_user()
    current_password = request.form.get('current_password', '')
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')
    
    # Validate current password
    if not user.check_password(current_password):
        flash('Current password is incorrect.', 'error')
        return redirect(url_for('profile'))
    
    # Validate new password
    is_valid, message = validate_password(new_password)
    if not is_valid:
        flash(message, 'error')
        return redirect(url_for('profile'))
    
    # Check password confirmation
    if new_password != confirm_password:
        flash('New passwords do not match.', 'error')
        return redirect(url_for('profile'))
    
    # Update password
    try:
        user.set_password(new_password)
        db.session.commit()
        flash('Password changed successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Failed to change password. Please try again.', 'error')
    
    return redirect(url_for('profile'))

@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500

@app.errorhandler(403)
def forbidden_error(error):
    return render_template('errors/403.html'), 403

@app.context_processor
def inject_user():
    """Make current user available in all templates"""
    return dict(current_user=get_current_user())

if __name__ == '__main__':
    app.run(debug=True)
