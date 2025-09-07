from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    role = db.Column(db.String(20), default='staff')  # 'admin' or 'staff'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Relationships
    transactions = db.relationship('Transaction', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check if provided password matches hash"""
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        """Check if user is admin"""
        return self.role == 'admin'
    
    def update_last_login(self):
        """Update last login timestamp"""
        self.last_login = datetime.utcnow()
        db.session.commit()

    def __repr__(self):
        return f'<User {self.username}>'

class Supplier(db.Model):
    __tablename__ = 'suppliers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    contact = db.Column(db.String(20))
    email = db.Column(db.String(120))
    address = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    products = db.relationship('Product', backref='supplier', lazy=True)

    def get_total_products(self):
        """Get total number of products from this supplier"""
        return len(self.products)
    
    def get_active_products(self):
        """Get active products from this supplier"""
        return [p for p in self.products if p.is_active]

    def __repr__(self):
        return f'<Supplier {self.name}>'

class Product(db.Model):
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    category = db.Column(db.String(50), nullable=False, index=True)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    min_stock_level = db.Column(db.Integer, default=10)  # Low stock alert threshold
    sku = db.Column(db.String(50), unique=True)  # Stock Keeping Unit
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    transactions = db.relationship('Transaction', backref='product', lazy=True, cascade='all, delete-orphan')

    def is_low_stock(self):
        """Check if product is low on stock"""
        return self.quantity <= self.min_stock_level
    
    def is_out_of_stock(self):
        """Check if product is out of stock"""
        return self.quantity <= 0
    
    def get_stock_status(self):
        """Get stock status as string"""
        if self.is_out_of_stock():
            return 'out_of_stock'
        elif self.is_low_stock():
            return 'low_stock'
        else:
            return 'in_stock'
    
    def get_total_value(self):
        """Get total value of current stock"""
        return self.quantity * self.price
    
    def update_stock(self, quantity_change, transaction_type, user_id, notes=None):
        """Update stock and create transaction record"""
        old_quantity = self.quantity
        
        if transaction_type == 'add':
            self.quantity += quantity_change
        elif transaction_type == 'remove':
            if self.quantity >= quantity_change:
                self.quantity -= quantity_change
            else:
                raise ValueError("Insufficient stock")
        
        # Create transaction record
        transaction = Transaction(
            product_id=self.id,
            user_id=user_id,
            transaction_type=transaction_type,
            quantity=quantity_change,
            old_quantity=old_quantity,
            new_quantity=self.quantity,
            notes=notes
        )
        
        db.session.add(transaction)
        db.session.commit()
        
        return transaction

    def __repr__(self):
        return f'<Product {self.name}>'

class Transaction(db.Model):
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    transaction_type = db.Column(db.String(10), nullable=False, index=True)  # 'add' or 'remove'
    quantity = db.Column(db.Integer, nullable=False)
    old_quantity = db.Column(db.Integer, nullable=False)  # Quantity before transaction
    new_quantity = db.Column(db.Integer, nullable=False)  # Quantity after transaction
    unit_price = db.Column(db.Float)  # Price at time of transaction
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def get_total_value(self):
        """Get total value of transaction"""
        if self.unit_price:
            return self.quantity * self.unit_price
        return 0

    def __repr__(self):
        return f'<Transaction {self.transaction_type} {self.quantity} of {self.product.name}>'

# Helper functions for database operations
def create_default_admin():
    """Create default admin user if none exists"""
    admin = User.query.filter_by(role='admin').first()
    if not admin:
        admin = User(
            username='admin',
            email='admin@inventory.com',
            role='admin'
        )
        admin.set_password('admin123')  # Change this in production
        db.session.add(admin)
        db.session.commit()
        return admin
    return None

def get_low_stock_products():
    """Get all products with low stock"""
    return Product.query.filter(
        Product.quantity <= Product.min_stock_level,
        Product.is_active == True
    ).all()

def get_out_of_stock_products():
    """Get all products that are out of stock"""
    return Product.query.filter(
        Product.quantity <= 0,
        Product.is_active == True
    ).all()

def get_inventory_stats():
    """Get overall inventory statistics"""
    total_products = Product.query.filter_by(is_active=True).count()
    total_suppliers = Supplier.query.filter_by(is_active=True).count()
    low_stock_count = len(get_low_stock_products())
    out_of_stock_count = len(get_out_of_stock_products())
    
    # Calculate total inventory value
    products = Product.query.filter_by(is_active=True).all()
    total_value = sum(p.get_total_value() for p in products)
    
    return {
        'total_products': total_products,
        'total_suppliers': total_suppliers,
        'low_stock_count': low_stock_count,
        'out_of_stock_count': out_of_stock_count,
        'total_value': total_value
    }
