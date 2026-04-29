# Champion Draft Advisor - Web Interface

A modern, League of Legends-themed web interface for the Champion Draft Assist Tool.

## Features

### 🎯 Draft State Management
- **Ally Picks**: Add up to 4 allied champions
- **Enemy Picks**: Add up to 5 enemy champions  
- **Bans**: Track up to 5 banned champions
- **Champion Pool**: Manage your personal champion pool

### 📊 Smart Recommendations
- **Best Overall**: Top recommendations regardless of your champion pool
- **Best From My Pool**: Personalized recommendations from champions you know
- **Real-time Updates**: Recommendations update as you modify the draft state

### 📈 Detailed Analysis
- **Score Breakdown**: Meta, Synergy, Counter, and Mastery scores
- **Visual Progress Bars**: Easy-to-read score visualization
- **Explanations**: Understand why each champion is recommended
- **Risk Assessment**: See potential weaknesses of each pick

## How to Use

### 1. Start the Web Server
```bash
python web_server.py
```

### 2. Open Your Browser
Navigate to: `http://127.0.0.1:5000`

### 3. Set Up Your Draft
1. **Add Champions**: Click the `+` slots to select champions
2. **Build Your Pool**: Type champion names in the "My Champion Pool" section
3. **Switch Tabs**: Toggle between "Best Overall" and "Best From My Pool"

### 4. Get Recommendations
- View ranked recommendations in the center panel
- Click any recommendation to see detailed analysis
- Use the score breakdown to understand the math behind each suggestion

## Interface Layout

```
┌─────────────────────────────────────────────────────────────┐
│ Draft Advisor | Patch 14.3    [Mid ▼]  [Best Overall] [Pool] │
├─────────────────────────────────────────────────────────────┤
│ ┌─────────────┐ ┌─────────────────────┐ ┌─────────────────┐ │
│ │ Ally Picks  │ │ Recommended Picks   │ │ Score Breakdown │ │
│ │ [+][+][+][+]│ │ 1. Sylas      94 ✓  │ │ ┌─────────────┐ │ │
│ │             │ │ 2. Orianna    89    │ │ │   Sylas     │ │ │
│ │ Enemy Picks │ │ 3. Ahri       85    │ │ │ Meta:    92 │ │ │
│ │ [+][+][+]   │ │                     │ │ │ Synergy: 88 │ │ │
│ │ [+][+]      │ │ • Strong patch pick │ │ │ Counter: 95 │ │ │
│ │             │ │ • Synergizes well   │ │ │ Mastery: 85 │ │ │
│ │ Bans        │ │ • AP balance        │ │ └─────────────┘ │ │
│ │ [+][+][+]   │ │                     │ │ Why This Works: │ │
│ │ [+][+]      │ │                     │ │ • Excellent...  │ │
│ │             │ │                     │ │ Draft Risks:    │ │
│ │ My Pool     │ │                     │ │ • Vulnerable... │ │
│ │ [Yasuo][Zed]│ │                     │ │                 │ │
│ └─────────────┘ └─────────────────────┘ └─────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Technical Details

### Built With
- **Backend**: Flask (Python)
- **Frontend**: Vanilla JavaScript + CSS
- **Styling**: Custom CSS with League of Legends theme
- **API**: RESTful endpoints for recommendations

### API Endpoints
- `GET /`: Main interface
- `POST /api/recommendations`: Get champion recommendations
- `GET /api/champions`: Get available champions list

### Champion Images
Place champion portrait images in `static/images/champions/` directory:
- Format: `{champion_id}.jpg` (e.g., `sylas.jpg`, `orianna.jpg`)
- Fallback: `default.jpg` for missing images
- Recommended size: 48x48px or larger

## Customization

### Adding Champion Images
1. Download champion portraits from Riot's Data Dragon
2. Save as `static/images/champions/{champion_id}.jpg`
3. Images will automatically load in the interface

### Modifying the Theme
Edit `static/css/style.css` to customize:
- Colors and gradients
- Layout and spacing  
- Animations and transitions
- Responsive breakpoints

### Extending Functionality
- Add new API endpoints in `src/interface/web_app.py`
- Modify the frontend logic in `static/js/app.js`
- Update the HTML template in `templates/index.html`

## Development

### Running in Development Mode
```bash
# Start with auto-reload
python web_server.py

# Or use Flask directly
export FLASK_APP=src.interface.web_app
export FLASK_ENV=development
flask run
```

### Production Deployment
For production use, consider:
- Using a WSGI server like Gunicorn
- Adding proper error handling and logging
- Implementing user authentication
- Adding champion image CDN integration
- Optimizing for mobile devices

## Troubleshooting

### Common Issues

**Port Already in Use**
```bash
# Kill existing Flask processes
pkill -f flask
# Or use a different port
python web_server.py --port 5001
```

**Missing Champion Images**
- All missing images fall back to `default.jpg`
- Check file paths and naming conventions
- Ensure images are in `static/images/champions/`

**API Errors**
- Check browser console for JavaScript errors
- Verify Flask server is running
- Check network requests in browser dev tools

### Browser Compatibility
- Modern browsers (Chrome 80+, Firefox 75+, Safari 13+)
- JavaScript ES6+ features required
- CSS Grid and Flexbox support needed

## Future Enhancements

- [ ] Real champion images integration
- [ ] Drag & drop champion selection
- [ ] Multiple role support
- [ ] User accounts and saved drafts
- [ ] Advanced filtering and search
- [ ] Mobile-responsive design improvements
- [ ] Real-time multiplayer draft simulation