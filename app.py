import dash
import os
import uuid
import datetime
import math
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from dash import Dash, html, dcc
from flask import Flask
from flask import request
from dash.dependencies import Input, Output, State, ALL, MATCH
from dash import callback_context
import json
import dash_bootstrap_components as dbc

# Add for Excel export
import pandas as pd
import io
from flask import send_file

# Database setup
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Models
class When2MeetEvent(Base):
    __tablename__ = 'when2meet_events'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    url = Column(String, unique=True, nullable=False)
    timezone = Column(String, nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    start_time = Column(String, nullable=False)  # e.g., '09:00'
    end_time = Column(String, nullable=False)    # e.g., '18:00'
    # Add more fields as needed

class When2MeetAvailability(Base):
    __tablename__ = 'when2meet_availability'
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey('when2meet_events.id'), nullable=False)
    user_name = Column(String, nullable=False)
    time_slot = Column(String, nullable=False)  # e.g., '2024-07-11T09:00'
    available = Column(Boolean, default=True)
    event = relationship('When2MeetEvent', backref='availabilities')

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

# Dash app scaffold
server = Flask(__name__)
app = Dash(__name__, server=server, suppress_callback_exceptions=True, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.title = '7525 When2Meet'

app.layout = html.Div([
    # Navbar
    html.Nav([
        html.Button('Plan a New Event', id='new-event-btn', style={
            'fontSize': '14px',
            'padding': '6px 12px',
            'margin': '8px',
            'borderRadius': '0px',
            'border': '0px solid transparent',
            'background': 'transparent',
            'color': '#fff',
            'cursor': 'pointer',
        }),
        html.Button('Admin', id='admin-btn', style={
            'fontSize': '14px',
            'padding': '6px 12px',
            'margin': '8px',
            'borderRadius': '0px',
            'border': '0px solid transparent',
            'background': 'transparent',
            'color': '#fff',
            'cursor': 'pointer',
        })
    ], style={
        'width': '100%',
        'display': 'flex',
        'justifyContent': 'flex-start',
        'alignItems': 'center',
        'background': '#5A8CC8',
        'padding': '0',
        'height': '40px',
        'boxSizing': 'border-box',
        'position': 'sticky',
        'top': '0',
        'zIndex': '1000',
    }),
    dcc.Location(id='url', refresh=False),
    dcc.Store(id='event-user-store'),  # Store for signed-in user
    dcc.Store(id='user-availability-store'),  # Store for user's local availability
    html.Div(id='page-content')
], style={'backgroundColor': '#1a1a1a', 'minHeight': '100vh', 'color': '#f5f5f5'})

def serve_homepage():
    hour_options = [{'label': str(h), 'value': str(h)} for h in range(1, 13)]
    minute_options = [{'label': f'{m:02d}', 'value': f'{m:02d}'} for m in [0, 15, 30, 45]]
    ampm_options = [{'label': 'AM', 'value': 'AM'}, {'label': 'PM', 'value': 'PM'}]
    dropdown_style = {'width': '60px', 'display': 'inline-block', 'marginRight': '4px', 'color': 'black'}
    ampm_style = {'width': '70px', 'display': 'inline-block', 'color': 'black'}
    return html.Div([
        html.Div([
            html.Img(src='/assets/logo.png', className='homepage-logo', style={
                'maxWidth': '180px', 'height': 'auto', 'marginRight': '48px', 'marginBottom': '0', 'display': 'block', 'borderRadius': '12px', 'boxShadow': '0 2px 8px rgba(0,0,0,0.08)'}),
            html.Div([
                html.H2('Plan a New Event', className='homepage-title'),
                html.Label('Event Name:'),
                dcc.Input(id='event-name', type='text', placeholder='e.g. Team Meeting', style={'width': '100%', 'marginBottom': '8px'}),
                html.Label('Time Zone:'),
                dcc.Dropdown(
                    id='timezone',
                    options=[
                        {'label': 'America/Chicago', 'value': 'America/Chicago'},
                        {'label': 'America/New_York', 'value': 'America/New_York'},
                        {'label': 'America/Los_Angeles', 'value': 'America/Los_Angeles'},
                        {'label': 'UTC', 'value': 'UTC'},
                        # Add more as needed
                    ],
                    value='America/Chicago',
                    style={'width': '100%', 'marginBottom': '8px', 'color': 'black'}
                ),
                html.Label('Date Range:'),
                dcc.DatePickerRange(
                    id='date-range',
                    min_date_allowed=None,
                    max_date_allowed=None,
                    style={'marginBottom': '8px'}
                ),
                html.Label('Start Time:'),
                html.Div([
                    dcc.Dropdown(id='start-hour', options=hour_options, value='9', style=dropdown_style),
                    dcc.Dropdown(id='start-minute', options=minute_options, value='00', style=dropdown_style),
                    dcc.Dropdown(id='start-ampm', options=ampm_options, value='AM', style=ampm_style)
                ], style={'marginBottom': '8px'}),
                html.Label('End Time:'),
                html.Div([
                    dcc.Dropdown(id='end-hour', options=hour_options, value='6', style=dropdown_style),
                    dcc.Dropdown(id='end-minute', options=minute_options, value='00', style=dropdown_style),
                    dcc.Dropdown(id='end-ampm', options=ampm_options, value='PM', style=ampm_style)
                ], style={'marginBottom': '16px'}),
                html.Button('Create Event', id='create-event-btn', n_clicks=0, style={
                    'width': '100%', 'fontSize': '16px', 'padding': '10px', 'background': '#E77D2E', 'color': 'white', 'border': 'none', 'borderRadius': '4px', 'cursor': 'pointer'
                }),
                html.Div(id='create-event-output', style={'marginTop': '16px'})
            ], className='homepage-form', style={'maxWidth': '350px', 'margin': '0 auto'})
        ], className='homepage-flex', style={
            'display': 'flex', 'flexDirection': 'row', 'alignItems': 'center', 'justifyContent': 'center', 'margin': '0 auto', 'maxWidth': '700px', 'width': '100%'}),
    ])

def get_event_grid(event):
    # Generate list of dates
    start_date = event.start_date.date()
    end_date = event.end_date.date()
    num_days = (end_date - start_date).days + 1
    dates = [start_date + datetime.timedelta(days=i) for i in range(num_days)]
    # Generate list of time slots (every 30 min)
    def parse_time(tstr):
        h, m = map(int, tstr.split(':'))
        return datetime.time(hour=h, minute=m)
    start_time = parse_time(event.start_time)
    end_time = parse_time(event.end_time)
    slots = []
    t = datetime.datetime.combine(datetime.date.today(), start_time)
    end_dt = datetime.datetime.combine(datetime.date.today(), end_time)
    while t <= end_dt:
        slots.append(t.time())
        t += datetime.timedelta(minutes=30)
    return dates, slots

def render_availability_grid(event, user_avail_set=None, signed_in=False, user_name=None):
    session = SessionLocal()
    availabilities = session.query(When2MeetAvailability).filter_by(event_id=event.id).all()
    session.close()
    dates, slots = get_event_grid(event)
    avail_dict = {}
    all_names = set()
    for a in availabilities:
        dt = a.time_slot.split('T')
        if len(dt) == 2:
            d, t = dt
            avail_dict.setdefault((d, t), []).append(a.user_name)
            all_names.add(a.user_name)
    if user_avail_set:
        for d, t in user_avail_set:
            all_names.add('You')
    all_names = sorted(all_names)
    all_counts = [len(v) for v in avail_dict.values()] or [1]
    max_count = max(all_counts)
    grid_header = [html.Th('', style={'cursor': 'default'})] + [
        html.Th([
            html.Div(date.strftime('%a'), style={'fontWeight': 'bold'}),
            html.Div(date.strftime('%b %d'), style={'fontSize': '12px'})
        ], id={'type': 'col-header', 'date': str(date)}, style={'cursor': 'pointer', 'userSelect': 'none'})
        for date in dates
    ]
    grid_rows = []
    popovers = []
    for slot in slots:
        row = [html.Td(
            slot.strftime('%#I:%M %p').replace('AM','AM').replace('PM','PM'),
            id={'type': 'row-header', 'time': slot.strftime('%H:%M')},
            style={
                'cursor': 'pointer',
                'userSelect': 'none',
                'fontWeight': 'bold',
                'position': 'sticky',
                'left': 0,
                'background': '#232323',
                'zIndex': 2,
                'minWidth': '60px',
                'maxWidth': '80px',
                'borderRight': '2px solid #5A8CC8',
            }
        )]
        for date in dates:
            key = (str(date), slot.strftime('%H:%M'))
            available_names = avail_dict.get(key, [])
            is_user = user_avail_set and key in user_avail_set
            # Only add 'You' if the user's actual name is not already in the list
            if is_user and user_name and user_name not in available_names:
                available_names = available_names + ['You']
            count = len(available_names)
            # Color scale: white to blue (#5A8CC8)
            if max_count == 1:
                blue = 200
            else:
                blue = int(255 - (count / max_count) * (255 - 140))  # 140 is the blue channel of #5A8CC8
            color = f'rgb({90 + (255-90)*(1-count/max_count):.0f},{140 + (255-140)*(1-count/max_count):.0f},{200 + (255-200)*(1-count/max_count):.0f})' if count > 0 else '#fff'
            cell_color = '#5A8CC8' if is_user else color
            border = '2px solid #1976d2' if is_user else '1px solid #ccc'
            cell_id = {'type': 'grid-cell', 'id': f"{str(date)}-{slot.strftime('%H:%M')}"}
            popover_id = {'type': 'popover', 'id': f"cell-{date}-{slot.strftime('%H-%M')}", 'date': str(date), 'time': slot.strftime('%H:%M')}
            popover_content = [
                html.Div([
                    html.B('Available: '),
                    html.Span(', '.join(available_names) if available_names else 'None')
                ])
            ]
            row.append(html.Td([
                html.Div(f'{count}', style={'fontWeight': 'bold', 'fontSize': '13px', 'color': 'black'}),
                html.Div('✓', style={'color': '#fff', 'fontSize': '16px'}) if is_user else None
            ], id=cell_id, style={
                'background': cell_color,
                'border': border,
                'width': '40px',
                'height': '32px',
                'textAlign': 'center',
                'cursor': 'pointer',
                'transition': 'background 0.2s',
                'position': 'relative',
            }))
            popovers.append(
                dbc.Popover([
                    dbc.PopoverHeader(f"{date.strftime('%a %b %d')} {slot.strftime('%I:%M %p')}", style={'fontSize': '14px'}),
                    dbc.PopoverBody(popover_content)
                ],
                id=popover_id,
                target=cell_id,
                trigger='hover',
                placement='auto',
                style={'zIndex': 2000},
                )
            )
        grid_rows.append(html.Tr(row))
    grid = html.Table([
        html.Thead(html.Tr(grid_header)),
        html.Tbody(grid_rows)
    ], style={'borderCollapse': 'collapse', 'margin': '0 auto'})
    # Wrap grid in a div with scroll cue class and right padding
    return html.Div([grid] + popovers, className='grid-scroll-cue', style={'overflowX': 'auto', 'maxWidth': '100vw', 'position': 'relative', 'paddingRight': '24px'})

def serve_event_page(event_id, user_name=None, user_avail_set=None, signed_in=False):
    session = SessionLocal()
    event = session.query(When2MeetEvent).filter_by(url=event_id).first()
    session.close()
    if not event:
        return html.Div([
            html.H2('Event Not Found'),
            html.P('Sorry, this event does not exist.')
        ])
    # Get the full event link
    base_url = request.host_url.rstrip('/')
    event_link = f"{base_url}/event/{event_id}"
    # Layout: event info at top, then sign-in, then grid, all centered and stacked
    return html.Div([
        html.Div([
            html.Div([
                html.B('Share this link to invite others:'),
                dcc.Input(value=event_link, readOnly=True, style={'width': '100%', 'marginTop': '8px', 'marginBottom': '16px', 'fontSize': '15px', 'background': '#232323', 'color': '#fff', 'border': '1px solid #5A8CC8', 'borderRadius': '4px'}),
                html.A(
                    "Export to Excel",
                    href=f"/export_availability/{event_id}",
                    target="_blank",
                    style={
                        'marginLeft': '12px',
                        'fontWeight': 'bold',
                        'color': '#E77D2E',
                        'textDecoration': 'underline',
                        'fontSize': '15px',
                        'cursor': 'pointer'
                    }
                )
            ], style={'maxWidth': '600px', 'margin': '0 auto', 'marginBottom': '12px', 'display': 'flex', 'alignItems': 'center'}),
            html.H2(event.name, style={'marginBottom': '0.5em'}),
            html.P(f"Timezone: {event.timezone}"),
            html.P(f"Date Range: {event.start_date.date()} to {event.end_date.date()}"),
            html.P(f"Time Range: {event.start_time} to {event.end_time}"),
            html.Hr(),
        ], style={'textAlign': 'center', 'maxWidth': '600px', 'margin': '0 auto'}),
        html.Div([
            html.Div([
                html.Label('Your Name:'),
                dcc.Input(id='event-username', type='text', placeholder='Enter your name', style={'width': '100%', 'marginBottom': '8px'}),
                html.Label('Password (optional):'),
                dcc.Input(id='event-password', type='password', placeholder='Optional', style={'width': '100%', 'marginBottom': '8px'}),
                html.Button('Sign In', id='event-signin-btn', n_clicks=0, style={
                    'width': '100%', 'fontSize': '16px', 'padding': '10px', 'background': '#E77D2E', 'color': 'white', 'border': 'none', 'borderRadius': '4px', 'cursor': 'pointer', 'marginBottom': '8px'
                }),
                html.Div(id='event-signin-output', style={'marginTop': '8px'})
            ], style={'maxWidth': '350px', 'margin': '0 auto', 'marginBottom': '24px'}),
            html.Div([
                html.H3("Group's Availability", style={'textAlign': 'center', 'marginBottom': '8px'}),
                html.Div([
                    html.Span('1/14 Available', style={'fontSize': '12px', 'marginRight': '8px'}),
                    html.Div(style={'display': 'inline-block', 'width': '80px', 'height': '16px', 'background': 'linear-gradient(to right, #fff, #5A8CC8)', 'verticalAlign': 'middle', 'marginRight': '8px'}),
                    html.Span('14/14 Available', style={'fontSize': '12px'})
                ], style={'textAlign': 'center', 'marginBottom': '4px'}),
                html.Div('Mouseover or click a cell to see who is available', style={'textAlign': 'center', 'fontSize': '12px', 'marginBottom': '8px'}),
                html.Div([
                    html.Div(render_availability_grid(event, user_avail_set, signed_in=bool(user_name), user_name=user_name), id='event-availability-grid', style={'overflowX': 'auto', 'maxWidth': '100vw', 'position': 'relative'}),
                    html.Div(id='grid-tooltip', style={
                        'display': 'none',
                        'position': 'fixed',
                        'zIndex': 9999,
                        'background': 'white',
                        'border': '1px solid #1976d2',
                        'borderRadius': '6px',
                        'padding': '8px',
                        'boxShadow': '0 2px 8px rgba(0,0,0,0.15)',
                        'fontSize': '13px',
                        'pointerEvents': 'none',
                        'minWidth': '180px',
                        'maxWidth': '260px',
                        'color': '#222',
                    })
                ], style={'position': 'relative'}),
                html.Button('Save My Availability', id='save-availability-btn', n_clicks=0, style={
                    'marginTop': '16px', 'width': '100%', 'fontSize': '16px', 'padding': '10px', 'background': '#E77D2E', 'color': 'white', 'border': 'none', 'borderRadius': '4px', 'cursor': 'pointer',
                    'display': 'block' if signed_in else 'none'
                }),
                html.Div(id='grid-message', style={'textAlign': 'center', 'color': '#d32f2f', 'marginTop': '8px'})
            ], style={'width': '100%', 'maxWidth': '600px', 'margin': '0 auto'})
        ], style={'display': 'flex', 'flexDirection': 'column', 'alignItems': 'center'})
    ])

# Interactivity for toggling availability will be implemented next.

@app.callback(
    dash.dependencies.Output('page-content', 'children'),
    [dash.dependencies.Input('url', 'pathname')]
)
def display_page(pathname):
    if pathname == '/admin':
        return serve_admin_page()
    if pathname and pathname.startswith('/event/'):
        event_id = pathname.split('/event/')[1]
        return serve_event_page(event_id)
    return serve_homepage()

@app.callback(
    Output('create-event-output', 'children'),
    Output('url', 'pathname'),
    Input('create-event-btn', 'n_clicks'),
    State('event-name', 'value'),
    State('timezone', 'value'),
    State('date-range', 'start_date'),
    State('date-range', 'end_date'),
    State('start-hour', 'value'),
    State('start-minute', 'value'),
    State('start-ampm', 'value'),
    State('end-hour', 'value'),
    State('end-minute', 'value'),
    State('end-ampm', 'value'),
    prevent_initial_call=True
)
def create_event(n_clicks, event_name, timezone, start_date, end_date, start_hour, start_minute, start_ampm, end_hour, end_minute, end_ampm):
    if not event_name or not timezone or not start_date or not end_date or not start_hour or not start_minute or not start_ampm or not end_hour or not end_minute or not end_ampm:
        return 'Please fill in all required fields.', dash.no_update
    # Convert to 24-hour format
    def to_24h(hour, minute, ampm):
        hour = int(hour)
        if ampm == 'AM':
            if hour == 12:
                hour = 0
        else:
            if hour != 12:
                hour += 12
        return f"{hour:02d}:{minute}"
    start_time = to_24h(start_hour, start_minute, start_ampm)
    end_time = to_24h(end_hour, end_minute, end_ampm)
    # Generate a unique URL for the event
    event_url = str(uuid.uuid4())[:8]
    try:
        session = SessionLocal()
        # Check for duplicate event URL (very unlikely)
        while session.query(When2MeetEvent).filter_by(url=event_url).first():
            event_url = str(uuid.uuid4())[:8]
        event = When2MeetEvent(
            name=event_name,
            url=event_url,
            timezone=timezone,
            start_date=start_date,
            end_date=end_date,
            start_time=start_time,
            end_time=end_time
        )
        session.add(event)
        session.commit()
        session.close()
        link = dcc.Link(f'Share this link: /event/{event_url}', href=f'/event/{event_url}', style={'fontWeight': 'bold', 'fontSize': '1.1em'})
        return link, f'/event/{event_url}'
    except Exception as e:
        return f'Error creating event: {e}', dash.no_update

@app.callback(
    Output('event-user-store', 'data'),
    Output('event-signin-output', 'children'),
    Input('event-signin-btn', 'n_clicks'),
    State('event-username', 'value'),
    State('event-password', 'value'),
    prevent_initial_call=True
)
def event_signin(n_clicks, username, password):
    if not username:
        return dash.no_update, 'Please enter your name to sign in.'
    # Store user info in dcc.Store (password is optional)
    return {'username': username, 'password': password}, f'Signed in as {username}'

@app.callback(
    Output('event-signin-section', 'style'),
    Output('availability-grid-section', 'children'),
    Input('event-user-store', 'data'),
    State('url', 'pathname'),
    prevent_initial_call=True
)
def show_grid_after_signin(user_data, pathname):
    if not user_data or not user_data.get('username'):
        return {}, ''
    # Placeholder for grid, will implement next
    return {'display': 'none'}, html.Div([
        html.H4(f"Welcome, {user_data['username']}!"),
        html.P('Availability grid will go here.')
    ])

# When user signs in, load their availability into the store
@app.callback(
    Output('user-availability-store', 'data', allow_duplicate=True),
    Input('event-user-store', 'data'),
    State('url', 'pathname'),
    prevent_initial_call=True
)
def load_user_availability(user_data, pathname):
    if not user_data or not user_data.get('username') or not pathname or '/event/' not in pathname:
        return {}
    event_id = pathname.split('/event/')[1]
    session = SessionLocal()
    event = session.query(When2MeetEvent).filter_by(url=event_id).first()
    if not event:
        session.close()
        return {}
    user_avail = set()
    for a in session.query(When2MeetAvailability).filter_by(event_id=event.id, user_name=user_data['username']):
        dt = a.time_slot.split('T')
        if len(dt) == 2:
            user_avail.add((dt[0], dt[1]))
    session.close()
    return list(user_avail)

# Pattern-matching callback for cell, row, and column header clicks
@app.callback(
    Output('user-availability-store', 'data', allow_duplicate=True),
    Output('grid-message', 'children', allow_duplicate=True),
    Input({'type': 'grid-cell', 'id': ALL}, 'n_clicks'),
    Input({'type': 'row-header', 'time': ALL}, 'n_clicks'),
    Input({'type': 'col-header', 'date': ALL}, 'n_clicks'),
    State('user-availability-store', 'data'),
    State('event-user-store', 'data'),
    State('url', 'pathname'),
    prevent_initial_call=True
)
def toggle_user_availability(cell_clicks, row_clicks, col_clicks, user_avail, user_data, pathname):
    ctx = callback_context
    if not ctx.triggered or not user_data or not user_data.get('username'):
        return dash.no_update, 'Sign in to edit your availability.'
    prop_id = ctx.triggered[0]['prop_id']
    print(f"DEBUG: Triggered prop_id: {prop_id}")  # Debug line
    print(f"DEBUG: All cell_clicks: {cell_clicks}")  # Debug line
    print(f"DEBUG: All row_clicks: {row_clicks}")  # Debug line
    print(f"DEBUG: All col_clicks: {col_clicks}")  # Debug line
    print(f"DEBUG: Which callback triggered: {ctx.triggered[0]['prop_id']}")  # Debug line
    user_avail = set(tuple(x) for x in (user_avail or []))
    # Handle cell click
    if 'grid-cell' in prop_id:
        print("DEBUG: Processing grid-cell click")  # Debug line
        cell_dict = json.loads(prop_id.split('.')[0])
        print(f"DEBUG: Cell dict: {cell_dict}")  # Debug line
        # Use the date and time properties directly from the cell ID
        id_parts = cell_dict['id'].split('-')
        date_str = f"{id_parts[0]}-{id_parts[1]}-{id_parts[2]}"
        time_str = id_parts[3]
        key = (date_str, time_str)
        print(f"DEBUG: Toggling key: {key}")  # Debug line
        if key in user_avail:
            user_avail.remove(key)
        else:
            user_avail.add(key)
        return list(user_avail), ''
    # Handle row header click
    if 'row-header' in prop_id:
        print("DEBUG: Processing row-header click")  # Debug line
        row_dict = json.loads(prop_id.split('.')[0])
        time = row_dict['time']
        # Find the index of the triggered row header
        triggered_idx = None
        for i, inp in enumerate(ctx.inputs_list[1]):
            if inp['id'] == row_dict:
                triggered_idx = i
                break
        if triggered_idx is None or row_clicks[triggered_idx] is None:
            print("DEBUG: Ignoring row-header click - not a real click")
            return dash.no_update, ''
        # Get all dates for this event
        event_id = pathname.split('/event/')[1]
        session = SessionLocal()
        event = session.query(When2MeetEvent).filter_by(url=event_id).first()
        session.close()
        if not event:
            return dash.no_update, 'Event not found.'
        start_date = event.start_date.date()
        end_date = event.end_date.date()
        num_days = (end_date - start_date).days + 1
        dates = [start_date + datetime.timedelta(days=i) for i in range(num_days)]
        # Build all keys for this row
        row_keys = [(str(date), time) for date in dates]
        # Toggle: if all are selected, clear; else, select all
        if all(key in user_avail for key in row_keys):
            for key in row_keys:
                user_avail.discard(key)
        else:
            for key in row_keys:
                user_avail.add(key)
        return list(user_avail), ''
    # Handle column header click
    if 'col-header' in prop_id:
        print("DEBUG: Processing col-header click")  # Debug line
        col_dict = json.loads(prop_id.split('.')[0])
        date = col_dict['date']
        # Find the index of the triggered col header
        triggered_idx = None
        for i, inp in enumerate(ctx.inputs_list[2]):
            if inp['id'] == col_dict:
                triggered_idx = i
                break
        if triggered_idx is None or col_clicks[triggered_idx] is None:
            print("DEBUG: Ignoring col-header click - not a real click")
            return dash.no_update, ''
        print(f"DEBUG: Column header date: {date}")  # Debug line
        # Get all times for this event
        event_id = pathname.split('/event/')[1]
        session = SessionLocal()
        event = session.query(When2MeetEvent).filter_by(url=event_id).first()
        session.close()
        if not event:
            return dash.no_update, 'Event not found.'
        def parse_time(tstr):
            h, m = map(int, tstr.split(':'))
            return datetime.time(hour=h, minute=m)
        start_time = parse_time(event.start_time)
        end_time = parse_time(event.end_time)
        slots = []
        t = datetime.datetime.combine(datetime.date.today(), start_time)
        end_dt = datetime.datetime.combine(datetime.date.today(), end_time)
        while t <= end_dt:
            slots.append(t.time())
            t += datetime.timedelta(minutes=30)
        col_keys = [(date, slot.strftime('%H:%M')) for slot in slots]
        # Toggle: if all are selected, clear; else, select all
        if all(key in user_avail for key in col_keys):
            for key in col_keys:
                user_avail.discard(key)
        else:
            for key in col_keys:
                user_avail.add(key)
        return list(user_avail), ''
    return dash.no_update, ''

# Render the grid with user's local availability
@app.callback(
    Output('event-availability-grid', 'children'),
    Input('user-availability-store', 'data'),
    State('event-user-store', 'data'),
    State('url', 'pathname'),
    prevent_initial_call=True
)
def render_grid(user_avail, user_data, pathname):
    if not pathname or '/event/' not in pathname:
        return dash.no_update
    event_id = pathname.split('/event/')[1]
    user_name = user_data['username'] if user_data and user_data.get('username') else None
    user_avail_set = set(tuple(x) for x in (user_avail or []))
    session = SessionLocal()
    event = session.query(When2MeetEvent).filter_by(url=event_id).first()
    session.close()
    if not event:
        return dash.no_update
    return render_availability_grid(event, user_avail_set, signed_in=bool(user_name), user_name=user_name)

# Save user's availability to the database
@app.callback(
    Output('grid-message', 'children', allow_duplicate=True),
    Input('save-availability-btn', 'n_clicks'),
    State('user-availability-store', 'data'),
    State('event-user-store', 'data'),
    State('url', 'pathname'),
    prevent_initial_call=True
)
def save_user_availability(n_clicks, user_avail, user_data, pathname):
    if not user_data or not user_data.get('username') or not pathname or '/event/' not in pathname:
        return 'Sign in to save your availability.'
    event_id = pathname.split('/event/')[1]
    session = SessionLocal()
    event = session.query(When2MeetEvent).filter_by(url=event_id).first()
    if not event:
        session.close()
        return 'Event not found.'
    # Remove all previous availabilities for this user/event
    session.query(When2MeetAvailability).filter_by(event_id=event.id, user_name=user_data['username']).delete()
    # Add new availabilities
    for d, t in (user_avail or []):
        slot_key = f'{d}T{t}'
        new_avail = When2MeetAvailability(
            event_id=event.id,
            user_name=user_data['username'],
            time_slot=slot_key,
            available=True
        )
        session.add(new_avail)
    session.commit()
    session.close()
    return 'Your availability has been saved! The group grid is now updated.'

# Add a callback to update the tooltip content and position
@app.callback(
    Output('grid-tooltip', 'children', allow_duplicate=True),
    Output('grid-tooltip', 'style', allow_duplicate=True),
    Input('event-availability-grid', 'n_mouseover'),
    Input({'type': 'grid-cell', 'id': ALL}, 'n_mouseover'),
    State('event-user-store', 'data'),
    State('user-availability-store', 'data'),
    State('url', 'pathname'),
    State('grid-tooltip', 'style'),
    prevent_initial_call=True
)
def show_grid_tooltip(grid_mouseover, cell_mouseovers, user_data, user_avail, pathname, tooltip_style):
    ctx = callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update
    # Don't show tooltips when user is signed in (editing their availability)
    if user_data and user_data.get('username'):
        style = tooltip_style.copy() if tooltip_style else {}
        style['display'] = 'none'
        return '', style
    # Find which cell was hovered
    prop_id = ctx.triggered[0]['prop_id']
    if 'grid-cell' not in prop_id:
        # Hide tooltip if not on a cell
        style = tooltip_style.copy() if tooltip_style else {}
        style['display'] = 'none'
        return '', style
    # Get cell id
    cell_id = json.loads(prop_id.split('.')[0].replace("'", '"'))
    id_parts = cell_id['id'].split('-')
    date = f"{id_parts[0]}-{id_parts[1]}-{id_parts[2]}"
    time = id_parts[3]
    # Get event and availability info
    if not pathname or '/event/' not in pathname:
        return dash.no_update, dash.no_update
    event_id = pathname.split('/event/')[1]
    session = SessionLocal()
    event = session.query(When2MeetEvent).filter_by(url=event_id).first()
    availabilities = session.query(When2MeetAvailability).filter_by(event_id=event.id).all() if event else []
    session.close()
    avail_dict = {}
    all_names = set()
    for a in availabilities:
        dt = a.time_slot.split('T')
        if len(dt) == 2:
            d, t = dt
            avail_dict.setdefault((d, t), []).append(a.user_name)
            all_names.add(a.user_name)
    user_avail_set = set(tuple(x) for x in (user_avail or []))
    if user_avail_set:
        for d, t in user_avail_set:
            all_names.add('You')
    all_names = sorted(all_names)
    key = (date, time)
    available_names = avail_dict.get(key, [])
    is_user = user_avail_set and key in user_avail_set
    # Only add 'You' if the user's actual name is not already in the list
    if is_user and user_data and user_data.get('username') not in available_names:
        available_names = available_names + ['You']
    # Tooltip content (compact: only available names, comma-separated)
    available_str = ', '.join(available_names) if available_names else 'None'
    tooltip_content = [
        html.Div([
            html.B('Available: '),
            html.Span(available_str)
        ])
    ]
    # Get mouse position from event (not available in Dash natively), so position tooltip at fixed offset
    style = tooltip_style.copy() if tooltip_style else {}
    style['display'] = 'block'
    style['top'] = '200px'   # Move further down
    style['left'] = '60vw'   # Move further right
    return tooltip_content, style

# Add a callback to show/hide the save button based on sign-in
@app.callback(
    Output('save-availability-btn', 'style', allow_duplicate=True),
    Input('event-user-store', 'data'),
    State('save-availability-btn', 'style'),
    prevent_initial_call=True
)
def toggle_save_button(user_data, current_style):
    style = current_style.copy() if current_style else {}
    style['display'] = 'block' if user_data and user_data.get('username') else 'none'
    return style

@app.callback(
    Output('url', 'pathname', allow_duplicate=True),
    Input('new-event-btn', 'n_clicks'),
    prevent_initial_call=True
)
def go_home_on_new_event(n_clicks):
    if n_clicks:
        return '/'
    return dash.no_update

@app.callback(
    Output('url', 'pathname', allow_duplicate=True),
    Input('admin-btn', 'n_clicks'),
    prevent_initial_call=True
)
def go_admin_on_btn(n_clicks):
    if n_clicks:
        return '/admin'
    return dash.no_update

# Admin page scaffold

def serve_admin_page():
    return html.Div([
        html.Div([
            html.H2('Admin Sign In', className='homepage-title'),
            html.Label('Admin Username:'),
            dcc.Input(id='admin-username', type='text', placeholder='Enter admin username', style={'width': '100%', 'marginBottom': '8px'}),
            html.Label('Admin Password:'),
            dcc.Input(id='admin-password', type='password', placeholder='Enter admin password', style={'width': '100%', 'marginBottom': '16px'}),
            html.Button('Sign In', id='admin-signin-btn', n_clicks=0, style={
                'width': '100%', 'fontSize': '16px', 'padding': '10px', 'background': '#E77D2E', 'color': 'white', 'border': 'none', 'borderRadius': '4px', 'cursor': 'pointer', 'marginBottom': '8px'
            }),
            html.Div(id='admin-signin-output', style={'marginTop': '8px'})
        ], style={'maxWidth': '350px', 'margin': '0 auto'}, className='admin-form')
    ])

def serve_admin_dashboard(message=None):
    # Fetch all events
    session = SessionLocal()
    events = session.query(When2MeetEvent).order_by(When2MeetEvent.id.desc()).all()
    event_rows = []
    for event in events:
        # Fetch availabilities for this event
        availabilities = session.query(When2MeetAvailability).filter_by(event_id=event.id).all()
        # Build user->date->set(times) mapping
        user_date_times = {}
        for a in availabilities:
            dt = a.time_slot.split('T')
            if len(dt) == 2:
                d, t = dt
                user_date_times.setdefault(a.user_name, {}).setdefault(d, set()).add(t)
        # Get all users and all dates for this event
        users = sorted(user_date_times.keys())
        start_date = event.start_date.date()
        end_date = event.end_date.date()
        num_days = (end_date - start_date).days + 1
        dates = [str(start_date + datetime.timedelta(days=i)) for i in range(num_days)]
        # Get all possible times for this event
        def parse_time(tstr):
            h, m = map(int, tstr.split(':'))
            return datetime.time(hour=h, minute=m)
        start_time = parse_time(event.start_time)
        end_time = parse_time(event.end_time)
        slots = []
        t = datetime.datetime.combine(datetime.date.today(), start_time)
        end_dt = datetime.datetime.combine(datetime.date.today(), end_time)
        while t <= end_dt:
            slots.append(t.time())
            t += datetime.timedelta(minutes=30)
        slot_strs = [s.strftime('%H:%M') for s in slots]
        # Helper to merge consecutive times into ranges
        def merge_times(times):
            times = sorted(times)
            ranges = []
            i = 0
            while i < len(times):
                start = times[i]
                j = i
                while j+1 < len(times) and (
                    datetime.datetime.strptime(times[j+1], '%H:%M') - datetime.datetime.strptime(times[j], '%H:%M')).seconds == 1800:
                    j += 1
                end = times[j]
                # Format nicely
                start_dt = datetime.datetime.strptime(start, '%H:%M')
                end_dt = datetime.datetime.strptime(end, '%H:%M') + datetime.timedelta(minutes=30)
                if start == end:
                    label = start_dt.strftime('%#I:%M%p').lower()
                else:
                    label = f"{start_dt.strftime('%#I:%M')}-{end_dt.strftime('%#I:%M%p').lower()}"
                ranges.append(label)
                i = j+1
            return ', '.join(ranges)
        # Build compact summary table
        if users:
            summary_table = html.Table([
                html.Thead(html.Tr([html.Th('User')] + [html.Th(datetime.datetime.strptime(d, '%Y-%m-%d').strftime('%a %b %d')) for d in dates])),
                html.Tbody([
                    html.Tr([
                        html.Td(user)
                    ] + [
                        html.Td(merge_times(user_date_times[user].get(d, [])) if d in user_date_times[user] else '—', style={'color': '#5a8cc8' if d in user_date_times[user] else '#aaa'})
                        for d in dates
                    ]) for user in users
                ])
            ], style={'margin': '8px 0 16px 0', 'background': '#232323', 'color': '#f5f5f5', 'borderRadius': '6px', 'fontSize': '13px', 'width': 'auto', 'textAlign': 'center'})
        else:
            summary_table = html.Div('No availabilities yet.', style={'fontSize': '13px', 'color': '#aaa', 'margin': '8px 0 16px 0'})
        event_rows.append(html.Tr([
            html.Td(event.name),
            html.Td(html.A(f'/event/{event.url}', href=f'/event/{event.url}', target='_blank', style={'color': '#E77D2E'})),
            html.Td(event.timezone),
            html.Td(f"{event.start_date.date()} to {event.end_date.date()}"),
            html.Td([
                html.Button('Delete', id={'type': 'delete-event-btn', 'id': event.id}, n_clicks=0, className='delete-btn', style={
                    'background': '#E77D2E', 'color': 'white', 'border': 'none', 'borderRadius': '4px', 'padding': '4px 10px', 'cursor': 'pointer', 'fontSize': '13px'
                })
            ])
        ]))
        # Add a summary row below each event
        event_rows.append(html.Tr([
            html.Td(summary_table, colSpan=5, style={'background': '#181818', 'padding': '8px 0 16px 0'})
        ]))
    session.close()
    table = html.Table([
        html.Thead(html.Tr([
            html.Th('Event Name'), html.Th('Link'), html.Th('Timezone'), html.Th('Date Range'), html.Th('Actions')
        ])),
        html.Tbody(event_rows)
    ], className='admin-dashboard-table')
    return html.Div([
        html.H2('Admin Dashboard'),
        html.P(message, style={'color': '#E77D2E'}) if message else None,
        html.Div(table, className='admin-dashboard-table-wrapper')
    ])

@app.callback(
    Output('admin-signin-output', 'children'),
    Output('page-content', 'children', allow_duplicate=True),
    Input('admin-signin-btn', 'n_clicks'),
    State('admin-username', 'value'),
    State('admin-password', 'value'),
    prevent_initial_call=True,
    allow_duplicate=True
)
def admin_signin(n_clicks, username, password):
    if not username or not password:
        return 'Please enter both username and password.', dash.no_update
    if username == 'admin' and password == 'Admin123':
        return '', serve_admin_dashboard()
    else:
        return 'Incorrect username or password.', dash.no_update

@app.callback(
    Output('page-content', 'children', allow_duplicate=True),
    Input({'type': 'delete-event-btn', 'id': ALL}, 'n_clicks'),
    State('page-content', 'children'),
    prevent_initial_call=True,
    allow_duplicate=True
)
def admin_delete_event(delete_clicks, page_content):
    ctx = callback_context
    if not ctx.triggered:
        return dash.no_update
    prop_id = ctx.triggered[0]['prop_id']
    try:
        btn_id = json.loads(prop_id.split('.')[0])['id']
        # Find the index of the triggered button
        idx = None
        for i, n in enumerate(delete_clicks):
            if n and n > 0:
                # Check if this is the triggered button
                triggered_btn = ctx.inputs_list[0][i]['id']
                if triggered_btn['id'] == btn_id:
                    idx = i
                    break
        if idx is None:
            return dash.no_update
        session = SessionLocal()
        # Delete availabilities first
        session.query(When2MeetAvailability).filter_by(event_id=btn_id).delete()
        session.query(When2MeetEvent).filter_by(id=btn_id).delete()
        session.commit()
        session.close()
        return serve_admin_dashboard(message='Event deleted.')
    except Exception as e:
        return serve_admin_dashboard(message=f'Error deleting event: {e}')

# After saving availability, refresh the page to show updated grid
@app.callback(
    Output('url', 'pathname', allow_duplicate=True),
    Input('save-availability-btn', 'n_clicks'),
    State('url', 'pathname'),
    prevent_initial_call=True
)
def refresh_page_after_save(n_clicks, pathname):
    if n_clicks and pathname and '/event/' in pathname:
        # Force a page refresh by redirecting to the same URL
        return pathname
    return dash.no_update

# Add Flask route for Excel export
@server.route('/export_availability/<event_id>')
def export_availability(event_id):
    session = SessionLocal()
    event = session.query(When2MeetEvent).filter_by(url=event_id).first()
    if not event:
        session.close()
        return "Event not found", 404
    # Get all availabilities for this event
    availabilities = session.query(When2MeetAvailability).filter_by(event_id=event.id).all()
    session.close()
    # Build user/date/time mapping
    user_date_times = {}
    for a in availabilities:
        dt = a.time_slot.split('T')
        if len(dt) == 2:
            d, t = dt
            user_date_times.setdefault(a.user_name, {}).setdefault(d, set()).add(t)
    users = sorted(user_date_times.keys())
    start_date = event.start_date.date()
    end_date = event.end_date.date()
    num_days = (end_date - start_date).days + 1
    dates = [str(start_date + datetime.timedelta(days=i)) for i in range(num_days)]
    # Get all possible times for this event
    def parse_time(tstr):
        h, m = map(int, tstr.split(':'))
        return datetime.time(hour=h, minute=m)
    start_time = parse_time(event.start_time)
    end_time = parse_time(event.end_time)
    slots = []
    t = datetime.datetime.combine(datetime.date.today(), start_time)
    end_dt = datetime.datetime.combine(datetime.date.today(), end_time)
    while t <= end_dt:
        slots.append(t.time())
        t += datetime.timedelta(minutes=30)
    slot_strs = [s.strftime('%H:%M') for s in slots]
    # Build a DataFrame: rows = users, columns = date+time, value = 1 if available else 0
    columns = []
    for d in dates:
        for t in slot_strs:
            columns.append(f"{d} {t}")
    data = []
    for user in users:
        row = []
        for d in dates:
            for t in slot_strs:
                row.append(1 if d in user_date_times[user] and t in user_date_times[user][d] else 0)
        data.append(row)
    df = pd.DataFrame(data, columns=columns, index=users)
    df.index.name = 'User'
    # Write to Excel in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Availability')
    output.seek(0)
    filename = f"when2meet_availability_{event_id}.xlsx"
    return send_file(output, download_name=filename, as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

if __name__ == '__main__':
    app.run(debug=False)
