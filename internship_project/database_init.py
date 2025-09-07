"""
Database initialization script
Run this script to set up the database with sample data
"""

from app import app, db
from models import User, Product, Supplier, Transaction, create_default_admin
from datetime import datetime, timedelta
import random

def create_sample_data():
    """Create sample data for testing"""
    
    with app.app_context():
        # Create sample suppliers
        suppliers_data = [
            {'name': 'Tech Solutions Inc.', 'contact': '+1-555-0101', 'email': 'contact@techsolutions.com', 'address': '123 Tech Street, Silicon Valley, CA'},
            {'name': 'Office Supplies Co.', 'contact': '+1-555-0102', 'email': 'sales@officesupplies.com', 'address': '456 Business Ave, New York, NY'},
            {'name': 'Electronics Wholesale', 'contact': '+1-555-0103', 'email': 'info@electronicswholesale.com', 'address': '789 Electronics Blvd, Austin, TX'},
            {'name': 'Furniture Direct', 'contact': '+1-555-0104', 'email': 'orders@furnituredirect.com', 'address': '321 Furniture Lane, Chicago, IL'},
        ]
        
        suppliers = []
        for supplier_data in suppliers_data:
            supplier = Supplier(**supplier_data)
            db.session.add(supplier)
            suppliers.append(supplier)
        
        db.session.commit()
        
        # Create sample products
        products_data = [
            {'name': 'Laptop Dell XPS 13', 'category': 'Electronics', 'description': 'High-performance ultrabook', 'price': 999.99, 'quantity': 25, 'min_stock_level': 5, 'sku': 'DELL-XPS13-001'},
            {'name': 'Office Chair Ergonomic', 'category': 'Furniture', 'description': 'Comfortable ergonomic office chair', 'price': 299.99, 'quantity': 15, 'min_stock_level': 3, 'sku': 'CHAIR-ERG-001'},
            {'name': 'Wireless Mouse', 'category': 'Electronics', 'description': 'Bluetooth wireless mouse', 'price': 29.99, 'quantity': 50, 'min_stock_level': 10, 'sku': 'MOUSE-WL-001'},
            {'name': 'A4 Paper Ream', 'category': 'Office Supplies', 'description': '500 sheets of A4 paper', 'price': 8.99, 'quantity': 100, 'min_stock_level': 20, 'sku': 'PAPER-A4-001'},
            {'name': 'Monitor 24 inch', 'category': 'Electronics', 'description': '24-inch LED monitor', 'price': 199.99, 'quantity': 8, 'min_stock_level': 5, 'sku': 'MON-24-001'},
            {'name': 'Desk Lamp LED', 'category': 'Office Supplies', 'description': 'Adjustable LED desk lamp', 'price': 45.99, 'quantity': 2, 'min_stock_level': 5, 'sku': 'LAMP-LED-001'},  # Low stock
            {'name': 'Keyboard Mechanical', 'category': 'Electronics', 'description': 'Mechanical gaming keyboard', 'price': 89.99, 'quantity': 0, 'min_stock_level': 3, 'sku': 'KB-MECH-001'},  # Out of stock
        ]
        
        for i, product_data in enumerate(products_data):
            product_data['supplier_id'] = suppliers[i % len(suppliers)].id
            product = Product(**product_data)
            db.session.add(product)
        
        db.session.commit()
        
        # Create sample staff user
        staff_user = User(
            username='staff',
            email='staff@inventory.com',
            role='staff'
        )
        staff_user.set_password('staff123')
        db.session.add(staff_user)
        db.session.commit()
        
        # Create sample transactions
        products = Product.query.all()
        users = User.query.all()
        
        for _ in range(20):
            product = random.choice(products)
            user = random.choice(users)
            transaction_type = random.choice(['add', 'remove'])
            quantity = random.randint(1, 10)
            
            # Create transaction with random date in the past 30 days
            days_ago = random.randint(0, 30)
            transaction_date = datetime.utcnow() - timedelta(days=days_ago)
            
            transaction = Transaction(
                product_id=product.id,
                user_id=user.id,
                transaction_type=transaction_type,
                quantity=quantity,
                old_quantity=product.quantity,
                new_quantity=product.quantity + (quantity if transaction_type == 'add' else -quantity),
                unit_price=product.price,
                notes=f'Sample {transaction_type} transaction',
                created_at=transaction_date
            )
            
            db.session.add(transaction)
        
        db.session.commit()
        print("Sample data created successfully!")

if __name__ == '__main__':
    create_sample_data()
