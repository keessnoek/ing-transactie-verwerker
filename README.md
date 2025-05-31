# ING Transaction Processor

A comprehensive Flask web application for processing, categorizing, and analyzing ING bank transaction data with interactive visualizations.

**Built collaboratively by [Kees Snoek](https://github.com/keessnoek) and Claude Sonnet 4**

## 🚀 Features

### Transaction Management
- **CSV Import**: Seamless import of ING transaction CSV files
- **Duplicate Detection**: Smart hash-based duplicate prevention
- **Data Validation**: Robust error handling and validation

### Categorization System
- **Manual Categorization**: Easy drag-and-drop category assignment
- **Bulk Operations**: Categorize multiple transactions at once
- **Smart Suggestions**: AI-powered categorization suggestions
- **Store-Based Bulk Assignment**: Automatically categorize by store name

### Interactive Analytics
- **Pivot Tables**: Interactive cross-tabulation by month and category
- **Clickable Cells**: Drill down into specific month/category combinations
- **Transaction Details**: Modal view with detailed transaction breakdowns
- **Real-time Statistics**: Dynamic calculation of totals and averages

### User Interface
- **Bootstrap 5**: Modern, responsive design
- **Real-time Search**: Filter transactions across all fields
- **Dynamic Loading**: Smooth AJAX interactions
- **Mobile Friendly**: Works on desktop, tablet, and mobile

## 🛠️ Technology Stack

- **Backend**: Python Flask
- **Database**: SQLite
- **Frontend**: Bootstrap 5, JavaScript (ES6)
- **Security**: CSRF protection, input validation
- **Version Control**: Git with professional workflow

## 📋 Prerequisites

- Python 3.7+
- Flask
- SQLite (included with Python)

## 🔧 Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/keessnoek/ing-transactie-verwerker.git
   cd ing-transactie-verwerker
   ```

2. **Install dependencies**
   ```bash
   pip install flask
   ```

3. **Run the application**
   ```bash
   python ing_transactieverwerker.py
   ```

4. **Open in browser**
   Navigate to `http://localhost:5000`

## 📊 Usage

### Getting Started (Nederlandse ING gebruikers)

1. **Download je transactiedata**:
   - Log in op Mijn ING
   - Ga naar Rekening overzicht
   - Kies 'Downloaden' → CSV formaat

2. **Import in de applicatie**:
   - Ga naar 'Importeren'
   - Upload je CSV bestand
   - Bekijk de import resultaten

3. **Categoriseer je transacties**:
   - Maak categorieën aan (Boodschappen, Auto, etc.)
   - Gebruik bulk-toewijzing voor efficiency
   - Bekijk suggesties voor automatische categorisering

4. **Analyseer je uitgaven**:
   - Bekijk de interactieve kruistabel
   - Klik op cellen voor gedetailleerde transacties
   - Filter en zoek door je data

## 🎯 Key Features in Detail

### Interactive Pivot Table
- Cross-tabulation of expenses by month and category
- Click any cell to see underlying transactions
- Real-time statistics and totals
- Year-over-year comparison

### Smart Categorization
- Pattern recognition for common merchants (DEKAMARKT, Albert Heijn, Shell, etc.)
- Bulk assignment by store name
- Learning from user behavior
- Suggestion engine for uncategorized transactions

### Data Security
- Local SQLite database (your data stays private)
- Hash-based duplicate detection
- Secure file upload handling
- No external API dependencies

## 🤝 Development Partnership

This project showcases the collaborative potential between human domain expertise and AI technical capabilities:

- **Kees Snoek**: Product vision, user requirements, testing, and Dutch banking domain knowledge
- **Claude Sonnet 4**: Technical architecture, code implementation, and feature development

The development process involved iterative design, real-time debugging, and continuous feature enhancement based on actual usage patterns.

## 📈 Technical Highlights

- **Efficient Hash Algorithm**: Prevents duplicate imports using SHA256-based transaction fingerprinting
- **Dynamic Frontend**: Modern JavaScript with Bootstrap 5 components
- **RESTful API Design**: Clean separation between frontend and backend
- **Responsive Design**: Works seamlessly across all device sizes
- **Professional Git Workflow**: Proper version control with meaningful commits

## 🔮 Future Enhancements

- Export functionality (CSV, Excel)
- Advanced reporting and charts
- Budget tracking and alerts
- Multi-bank support
- Data visualization improvements

## 📄 License

This project is open source and available for personal use.

## 🙏 Acknowledgments

- Built with Flask framework
- Bootstrap 5 for UI components
- ING Bank for providing accessible transaction data
- The collaborative power of human-AI partnership

---

*This project demonstrates the potential of human-AI collaboration in creating practical, user-focused applications. From initial concept to production-ready tool, every feature was developed through iterative partnership between domain expertise and technical implementation.*
