#  vim: set ts=4 sw=4 tw=0 et :
"""Baby tracker
"""

import collections.abc
import configparser
import datetime as dt
import functools
import json
import os.path
import pathlib
import lxml.etree as xml

import dash
from dash import html, dcc, Input, Output, State, ALL, ctx
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine
import babel.dates as bd


PROJECT_DIR = pathlib.Path(__file__).resolve().parents[1]
DATA_DIR = os.path.join(PROJECT_DIR, 'data')

config = configparser.ConfigParser()
config.read(os.path.join(DATA_DIR, 'config.ini'))

SERVER_TZ = dt.datetime.utcnow().astimezone().tzinfo
BIRTH_DATE = dt.datetime.fromisoformat(config['baby']['birth']).astimezone(SERVER_TZ).replace(tzinfo=None)
NAME = config['baby']['name']
LOCALE = config['settings'].get('locale', 'de_DE')
ENGINE = create_engine(f'sqlite:////{DATA_DIR}/{config["settings"]["database"]}')
TABLE_PAGE_SIZE = 5

FEEDING_SOURCES = [
    {
        'key': 'breastmilk',
        'value': 'Muttermilch',
        'icon': 'person-breastfeeding'
    },
    {
        'key': 'preHA',
        'value': 'pre HA',
        'icon': 'cow'
    },
]

# Source: Bhutani et al. Pediatrics. 1999 Jan;103(1):6-14
# https://www.thieme.de/de/hebammenarbeit/hyperbilirubinaemie-neugeborenen-122829.htm
# Unit: mg/dL
#
HYPERBILIRUBINEMIA = {
    'column_names': ['percentile'],
    'columns': ['40th', '75th', '95th'],
    'data': [
        [4.75, 5.8, 7.25],
        [5.0, 6.4, 7.9],
        [5.6, 7.0, 8.9],
        [7.75, 9.9, 12.2],
        [8.1, 10.2, 12.5],
        [8.6, 10.9, 13.1],
        [9.6, 12.7, 15.1],
        [11.1, 13.25, 15.9],
        [11.75, 14.7, 16.75],
        [12.4, 15.1, 17.4],
        [13.25, 15.75, 17.6],
        [13.1, 15.5, 17.5],
        [13.1, 15.5, 17.5],
    ],
    'index': [20, 24, 28, 40, 44, 48, 60, 72, 84, 96, 120, 132, 168],
    'index_names': ['age'],
}


def generate_bilirubin_figure(data=None):
    """
    Arguments:
        data: measured values for current baby as indexed Series of
              bilirubin[µmol/l] vs age/[h]
    Factor: 1mg/dl = 17.1µmol/l
    Source: https://www.gastro.medline.ch/Services/_Tools/Um_und_Berechnungen/Umrechnung_von_mg_dl_mol_l.php
    """
    df = pd.DataFrame.from_dict(HYPERBILIRUBINEMIA, orient='tight').multiply(17.1)
    color_map = {
        '40th': px.colors.qualitative.Plotly[2],
        '75th': px.colors.qualitative.Plotly[0],
        '95th': px.colors.qualitative.Plotly[1],
    }
    fig = px.area(
        df,
        color_discrete_map=color_map,
        template='none',
        labels={'age': 'Alter [h]'},
        markers=True,
    ).update_layout(
        yaxis={'title': 'Bilirubin [µmol/l]'}
    )
    if data is not None:
        fig.add_trace(
            go.Scatter(
                name='baby',
                x=data.index,
                y=data,
                mode='lines+markers',
                marker=dict(
                    color='LightSkyBlue',
                    size=10,
                    line=dict(
                        color='MediumPurple',
                        width=2,
                    ),
                ),
                line=go.scatter.Line(color='gray'),
                showlegend=True)
        )
    return dcc.Graph(figure=fig)


def deep_update(data, update):
    for key, value in update.items():
        if isinstance(value, collections.abc.Mapping):
            data[key] = deep_update(data.get(key, {}), value)
        elif isinstance(value, collections.abc.MutableSequence):
            new = data.get(key, [])
            new.extend(value)
            data[key] = new
        else:
            data[key] = value
    return data


def generate_table(**kwargs):
    default = dict(
        page_current=0,
        page_size=TABLE_PAGE_SIZE,
        row_deletable=True,
        tooltip_duration=None,
        hidden_columns=['time', 'age'],
        markdown_options={'html': True},
        merge_duplicate_headers=True,
        columns=[
            {
                'id': 'time',
                'name': ['time', 'date'],
            },
            {
                'id': 'delta',
                'name': ['time', 'delta'],
            },
            {
                'id': 'age',
                'name': ['time', 'age'],
            },
        ],
        css=[
            {
                'selector': '.column-header--hide',
                'rule': 'display: none',
            },
            {
                'selector': 'p',  # markdown cells wrap icons
                'rule': 'margin: 0; text-align: center',
            },
            {
                'selector': '.fa-circle.smoke',
                'rule': 'color: WhiteSmoke',
            },
            {
                'selector': '.fa-circle-check',
                'rule': 'color: green',
            },
            {
                'selector': '.fa-circle-xmark',
                'rule': 'color: red',
            },
        ],
        style_table={
            'overflow': 'auto',
            'minWidth': '100%',
        },
        style_data_conditional=[],
        style_data={
            'whiteSpace': 'normal',
            'height': 'auto',
        },
        style_filter_conditional=[],
        style_filter={},
        style_header_conditional=[],
        style_header={
            'whiteSpace': 'normal',
            'overflow': 'auto',
            'textAlign': 'center',
        },
        style_cell={
            'maxWidth': 0,
        },
    )
    settings = deep_update(default, kwargs)
    for column in settings.get('columns', {}):
        column.update({
            'hideable': 'last',
        })
        if column.get('type') == 'boolean':
            column.update({
                'type': 'text',
                'presentation': 'markdown',
            })
    return dash.dash_table.DataTable(**settings)


@functools.cache
def generate_fa_icon(icon, **kwargs):
    """create a fontawesome circled icon with background

    See: https://fontawesome.com/docs/web/style/stack

    >>> print(generate_fa_icon('xmark', pretty_print=True))
    <span class="fa-stack">
      <i class="fa-stack-1x fa-solid fa-circle smoke"></i>
      <i class="fa-stack-1x fa-solid fa-circle-xmark"></i>
    </span>
    <BLANKLINE>
    """
    fa_icon_xml = xml.Element('span', attrib={'class': 'fa-stack'})
    icon_class = 'fa-stack-1x fa-solid'
    child = xml.SubElement(fa_icon_xml, 'i')
    child.set('class', f'{icon_class} fa-circle smoke')
    child.text = ''  # # do not collapse empty elements
    child = xml.SubElement(fa_icon_xml, 'i')
    child.set('class', f'{icon_class} fa-circle-{icon}')
    child.text = ''  # # do not collapse empty elements
    kwargs.update({
        'encoding': 'unicode',
    })
    return xml.tostring(fa_icon_xml, **kwargs)


app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.CERULEAN,
        dbc.icons.FONT_AWESOME,
    ],
)
app.layout = html.Div([
    dbc.NavbarSimple(
        brand='BabyTracker',
        brand_href='#',
        children=[
            dbc.NavItem(dbc.NavLink('Dateneingabe', href='#')),
            dbc.NavItem(dbc.NavLink('Account', href='/account')),
        ],
    ),
    html.Div([
        html.H1([html.I(className='fa-solid fa-baby me-2'), NAME]),
    ]),
    dbc.Accordion(
        always_open=True,
        flush=True,
        active_item=[
            'time',
            # 'drink',
            # 'diaper',
            # 'pump',
            # 'doctor',
        ],
        children=[
            dbc.AccordionItem(
                title='Zeit',
                item_id='time',
                children=[html.Div(
                    className='d-grid gap-2',
                    children=[
                        dbc.InputGroup([
                            dbc.Button(
                                html.I(className='fa-solid fa-rotate'),
                                id='update-date-time',
                                outline=True,
                            ),
                            dbc.Input(
                                id='date-time',
                                type='datetime-local',
                                min=BIRTH_DATE.isoformat(),
                            ),
                            dbc.InputGroupText(id='dt-output-container'),
                        ], className='mb-3'),
                    ],
                )],
            ),
            dbc.AccordionItem(
                title='Trinken',
                item_id='drink',
                children=[html.Div(
                    className='d-grid gap-2',
                    children=[
                        dbc.InputGroup([
                            dbc.InputGroupText(
                                children=[
                                    html.I(className=f'fa-solid fa-{source.get("icon")} me-2'),
                                    source.get('value'),
                                ],
                                class_name='w-50 me-2'
                            ),
                            dbc.Input(
                                id={'index': source.get('key'), 'type': 'drink'},
                                type='number',
                                pattern='[0-9]*',
                                placeholder=0,
                            ),
                            dbc.InputGroupText('ml'),
                        ]) for source in FEEDING_SOURCES
                    ] + [
                        dbc.InputGroup(
                            children=[
                                dbc.InputGroupText(
                                    children=[
                                        html.I(className='fa-solid fa-circle-arrow-left me-2'),
                                        'Brust links',
                                    ],
                                    class_name='w-50 me-2'
                                ),
                                dbc.InputGroupText(
                                    dbc.Switch(
                                        id={'index': 'breast-left', 'type': 'drink'},
                                        value=False,
                                    ),
                                    class_name='bg-transparent border-0',
                                ),
                            ],
                        ),
                        dbc.InputGroup(
                            children=[
                                dbc.InputGroupText(
                                    children=[
                                        html.I(className='fa-solid fa-circle-arrow-right me-2'),
                                        'Brust rechts',
                                    ],
                                    class_name='w-50 me-2'
                                ),
                                dbc.InputGroupText(
                                    dbc.Switch(
                                        id={'index': 'breast-right', 'type': 'drink'},
                                        value=False,
                                    ),
                                    class_name='bg-transparent border-0',
                                ),
                            ],
                        ),
                        dbc.Button(
                            'Update',
                            id={'index': 'drink', 'type': 'update'},
                            outline=True,
                            color='primary',
                            disabled=False,
                        ),
                        dcc.Store(id={'index': 'drink', 'type': 'store'}),
                        html.Div(id={'index': 'drink', 'type': 'debug'}, className='row visually-hidden'),
                        dbc.Tabs(
                            id={'index': 'drink', 'type': 'tabs'},
                            active_tab='table',
                            children=[
                                dbc.Tab(
                                    dbc.Card(generate_table(
                                        id={'index': 'drink', 'type': 'table'},
                                        columns=[
                                            {
                                                'id': 'breastmilk',
                                                'name': ['drink', 'breastmilk'],
                                                'type': 'numeric',
                                            },
                                            {
                                                'id': 'preHA',
                                                'name': ['volume', 'preHA'],
                                                'type': 'numeric',
                                            },
                                            {
                                                'id': 'breast-left',
                                                'name': ['breast', 'left'],
                                                'type': 'boolean',
                                            },
                                            {
                                                'id': 'breast-right',
                                                'name': ['breast', 'right'],
                                                'type': 'boolean',
                                            },
                                        ],
                                        style_cell_conditional=[
                                            {
                                                'if': {'column_id': 'breast-left'},
                                                'width': '10%',
                                            },
                                            {
                                                'if': {'column_id': 'breast-right'},
                                                'width': '10%',
                                            },
                                        ],
                                    )),
                                    label='Tabelle',
                                    tab_id='table',
                                ),
                                dbc.Tab(
                                    dbc.Card(id={'index': 'drink', 'type': 'graph'}),
                                    label='Graph',
                                    tab_id='graph',
                                ),
                            ],
                        ),
                    ],
                )],
            ),
            dbc.AccordionItem(
                title='Windel',
                item_id='diaper',
                children=[html.Div(
                    className='d-grid gap-2',
                    children=[
                        dbc.InputGroup(
                            children=[
                                dbc.InputGroupText(
                                    children=[
                                        html.I(className='fa-solid fa-user-nurse me-2'),
                                        'gewickelt',
                                    ],
                                    class_name='w-50 me-2'
                                ),
                                dbc.InputGroupText(
                                    dbc.Switch(
                                        id={'index': 'changed', 'type': 'diaper'},
                                        value=True,
                                    ),
                                    class_name='bg-transparent border-0',
                                ),
                            ],
                        ),
                        dbc.Collapse(
                            id='diaper-pee-collapse',
                            is_open=False,
                            children=[
                                dbc.InputGroup(
                                    children=[
                                        dbc.InputGroupText(
                                            children=[
                                                html.I(className='fa-solid fa-water me-2'),
                                                'pipi',
                                            ],
                                            class_name='w-50 me-2'
                                        ),
                                        dbc.InputGroupText(
                                            children=[
                                                dbc.Switch(
                                                    id={'index': 'pee', 'type': 'diaper'},
                                                    value=False,
                                                ),
                                                dbc.Input(
                                                    type='color',
                                                    id={'index': 'pee-color', 'type': 'diaper'},
                                                    value='#F8E45C',
                                                    disabled=True,
                                                    class_name='h-100 p-1 col-1',
                                                ),
                                            ],
                                            class_name='bg-transparent border-0',
                                        ),
                                    ],
                                ),
                            ],
                        ),
                        dbc.Collapse(
                            id='diaper-poo-collapse',
                            is_open=False,
                            children=[
                                dbc.InputGroup(
                                    children=[
                                        dbc.InputGroupText(
                                            children=[
                                                html.I(className='fa-solid fa-poo me-2'),
                                                'kaka',
                                            ],
                                            class_name='w-50 me-2'
                                        ),
                                        dbc.InputGroupText(
                                            children=[
                                                dbc.Switch(
                                                    id={'index': 'poo', 'type': 'diaper'},
                                                    value=False,
                                                ),
                                                dbc.Input(
                                                    type='color',
                                                    id={'index': 'poo-color', 'type': 'diaper'},
                                                    value='#865E3C',
                                                    class_name='h-100 p-1 col-1',
                                                ),
                                            ],
                                            class_name='bg-transparent border-0',
                                        ),
                                    ],
                                ),
                            ],
                        ),
                        dbc.Button(
                            'Update',
                            id={'index': 'diaper', 'type': 'update'},
                            outline=True,
                            color='primary',
                            disabled=False,
                        ),
                        dcc.Store(id={'index': 'diaper', 'type': 'store'}),
                        html.Div(id={'index': 'diaper', 'type': 'debug'}, className='row visually-hidden'),
                        dbc.Tabs(
                            id={'index': 'diaper', 'type': 'tabs'},
                            active_tab='table',
                            children=[
                                dbc.Tab(
                                    dbc.Card(generate_table(
                                        id={'index': 'diaper', 'type': 'table'},
                                        columns=[
                                            {
                                                'id': 'changed',
                                                'name': ['diaper', 'changed'],
                                                'type': 'boolean',
                                            },
                                            {
                                                'id': 'pee',
                                                'name': ['pee', 'present'],
                                                'type': 'boolean',
                                            },
                                            {
                                                'id': 'pee-color',
                                                'name': ['pee', 'color'],
                                                'type': 'text',
                                            },
                                            {
                                                'id': 'poo',
                                                'name': ['poo', 'present'],
                                                'type': 'boolean',
                                            },
                                            {
                                                'id': 'poo-color',
                                                'name': ['poo', 'color'],
                                                'type': 'text',
                                            },
                                        ],
                                        hidden_columns=['poo-color', 'pee-color'],
                                    )),
                                    label='Tabelle',
                                    tab_id='table',
                                ),
                                dbc.Tab(
                                    dbc.Card(id={'index': 'diaper', 'type': 'graph'}),
                                    label='Graph',
                                    tab_id='graph',
                                ),
                            ],
                        ),
                    ],
                )],
            ),
            dbc.AccordionItem(
                title='Milchpumpe',
                item_id='pump',
                children=[html.Div(
                    className='d-grid gap-2',
                    children=[
                        dbc.InputGroup(
                            children=[
                                dbc.InputGroupText(
                                    children=[
                                        html.I(className='fa-solid fa-person-breastfeeding me-2'),
                                        'Brust links',
                                    ],
                                    class_name='w-50 me-2'
                                ),
                                dbc.Input(
                                    id={'index': 'left', 'type': 'pump'},
                                    type='number',
                                    pattern='[0-9]*',
                                    placeholder=0,
                                ),
                                dbc.InputGroupText('ml'),
                            ],
                        ),
                        dbc.InputGroup(
                            children=[
                                dbc.InputGroupText(
                                    children=[
                                        html.I(className='fa-solid fa-person-breastfeeding me-2'),
                                        'Brust rechts',
                                    ],
                                    class_name='w-50 me-2'
                                ),
                                dbc.Input(
                                    id={'index': 'right', 'type': 'pump'},
                                    type='number',
                                    pattern='[0-9]*',
                                    placeholder=0,
                                ),
                                dbc.InputGroupText('ml'),
                            ],
                        ),
                        dbc.Button(
                            'Update',
                            id={'index': 'pump', 'type': 'update'},
                            outline=True,
                            color='primary',
                            disabled=False,
                        ),
                        dcc.Store(id={'index': 'pump', 'type': 'store'}),
                        html.Div(id={'index': 'pump', 'type': 'debug'}, className='row visually-hidden'),
                        dbc.Tabs(
                            id={'index': 'pump', 'type': 'tabs'},
                            active_tab='table',
                            children=[
                                dbc.Tab(
                                    dbc.Card(generate_table(
                                        id={'index': 'pump', 'type': 'table'},
                                        columns=[
                                            {
                                                'id': 'left',
                                                'name': ['breast', 'left'],
                                                'type': 'numeric',
                                            },
                                            {
                                                'id': 'right',
                                                'name': ['breast', 'right'],
                                                'type': 'numeric',
                                            },
                                        ],
                                    )),
                                    label='Tabelle',
                                    tab_id='table',
                                ),
                                dbc.Tab(
                                    dbc.Card(id={'index': 'pump', 'type': 'graph'}),
                                    label='Graph',
                                    tab_id='graph',
                                ),
                            ],
                        ),
                    ],
                )],
            ),
            dbc.AccordionItem(
                title='Arzt',
                item_id='doctor',
                children=[html.Div(
                    className='d-grid gap-2',
                    children=[
                        dbc.InputGroup(
                            children=[
                                dbc.InputGroupText(
                                    children=[
                                        html.I(className='fa-solid fa-weight-scale me-2'),
                                        'Gewicht',
                                    ],
                                    class_name='w-50 me-2'
                                ),
                                dbc.Input(
                                    id={'index': 'weight', 'type': 'doctor'},
                                    type='number',
                                    pattern='[0-9]*',
                                    placeholder=None,
                                ),
                                dbc.InputGroupText('g'),
                            ],
                        ),
                        dbc.InputGroup(
                            children=[
                                dbc.InputGroupText(
                                    children=[
                                        html.I(className='fa-solid fa-ruler me-2'),
                                        'Kopfumfang',
                                    ],
                                    class_name='w-50 me-2'
                                ),
                                dbc.Input(
                                    id={'index': 'circumference', 'type': 'doctor'},
                                    type='number',
                                    pattern='[0-9]*',
                                    placeholder=None,
                                ),
                                dbc.InputGroupText('mm'),
                            ],
                        ),
                        dbc.InputGroup(
                            children=[
                                dbc.InputGroupText(
                                    children=[
                                        html.I(className='fa-solid fa-vial me-2'),
                                        'Bilirubin',
                                    ],
                                    class_name='w-50 me-2'
                                ),
                                dbc.Input(
                                    id={'index': 'bilirubin', 'type': 'doctor'},
                                    type='number',
                                    pattern='[0-9]*',
                                    placeholder=None,
                                ),
                                dbc.InputGroupText('µmol/l'),
                            ],
                        ),
                        dbc.Button(
                            'Update',
                            id={'index': 'doctor', 'type': 'update'},
                            outline=True,
                            color='primary',
                            disabled=False,
                        ),
                        dcc.Store(id={'index': 'doctor', 'type': 'store'}),
                        html.Div(
                            id={'index': 'doctor', 'type': 'debug'},
                            className='row visually-hidden',
                        ),
                        dbc.Tabs(
                            id={'index': 'doctor', 'type': 'tabs'},
                            active_tab='table',
                            children=[
                                dbc.Tab(
                                    dbc.Card(generate_table(
                                        id={'index': 'doctor', 'type': 'table'},
                                        columns=[
                                            {
                                                'id': 'weight',
                                                'name': ['measures', 'weight'],
                                                'type': 'numeric',
                                            },
                                            {
                                                'id': 'circumference',
                                                'name': ['measures', 'circumference'],
                                                'type': 'numeric',
                                            },
                                            {
                                                'id': 'bilirubin',
                                                'name': ['measures', 'bilirubin'],
                                                'type': 'numeric',
                                            },
                                        ],
                                    )),
                                    label='Tabelle',
                                    tab_id='table',
                                ),
                                dbc.Tab(
                                    dbc.Card(id={'index': 'doctor', 'type': 'graph'}),
                                    label='Graph',
                                    tab_id='graph',
                                ),
                                dbc.Tab(
                                    dbc.Card(
                                        children=[
                                            dbc.CardBody(
                                                id={'index': 'bilirubin', 'type': 'figure'},
                                                children=generate_bilirubin_figure(),
                                            ),
                                            dbc.CardFooter(
                                                dcc.Link(
                                                    'Bhutani et al. Pediatrics. 1999 Jan;103(1):6-14',
                                                    href='https://doi.org/10.1542/peds.103.1.6',
                                                    target='_blank',
                                                )
                                            )
                                        ],
                                    ),
                                    label='Bilirubin',
                                    tab_id='bilirubin',
                                ),
                            ],
                        ),
                    ],
                )],
            ),
        ],
    ),
])


@app.callback(
    Output('dt-output-container', 'children'),
    Input('date-time', 'value'),
)
def update_output(date_value):
    """Update Date picker"""
    if date_value is None:
        date_object = dt.datetime.now()
    else:
        date_object = dt.datetime.fromisoformat(date_value)
    age = date_object - BIRTH_DATE
    hours, temp = divmod(age.seconds, dt.timedelta(hours=1).seconds)
    minutes = temp // dt.timedelta(minutes=1).seconds
    return f'{age.days}d{hours}h{minutes}m'


@app.callback(
    Output('diaper-pee-collapse', 'is_open'),
    Output('diaper-poo-collapse', 'is_open'),
    Input({'index': 'changed', 'type': 'diaper'}, 'value'),
)
def show_diaper_full(diaper_changed):
    """Show Collapsed Inputs if diaper changed."""
    is_open = bool(diaper_changed)
    return is_open, is_open


@app.callback(
    Output({'index': 'pee-color', 'type': 'diaper'}, 'disabled'),
    Input({'index': 'pee', 'type': 'diaper'}, 'value'),
)
def show_diaper_pee_color(diaper_pee):
    """Enable Color input if pee is checked."""
    return not bool(diaper_pee)


@app.callback(
    Output({'index': 'poo-color', 'type': 'diaper'}, 'disabled'),
    Input({'index': 'poo', 'type': 'diaper'}, 'value'),
)
def show_diaper_poo(diaper_poo):
    """Enable Color input if poo is checked."""
    return not bool(diaper_poo)


for category in ['drink', 'diaper', 'pump', 'doctor']:
    @app.callback(
        Output({'index': category, 'type': 'store'}, 'data'),
        Input('date-time', 'value'),
        Input({'index': ALL, 'type': category}, 'value'),
        Input({'index': ALL, 'type': category}, 'id'),
        Input({'index': ALL, 'type': category}, 'disabled'),
    )
    def on_update_data(time, values, ids, disabled):
        """Enable Color input if poo is checked."""
        inputs = dict(zip([i['index'] for i in ids], values))
        for key, value in zip(ids, disabled):
            if value:
                inputs[key['index']] = None
        inputs['time'] = time
        inputs['type'] = ids[0].get('type')
        return inputs

    @app.callback(
        Output({'index': category, 'type': 'update'}, 'color'),
        Output({'index': category, 'type': 'update'}, 'disabled'),
        Input({'index': category, 'type': 'update'}, 'n_clicks'),
        Input({'index': category, 'type': 'store'}, 'data'),
        prevent_initial_call=True,
    )
    def on_click_update(_, store):
        triggered = [p['type'] for p in ctx.triggered_prop_ids.values()]
        if 'store' in triggered:
            return 'primary', False
        store_category = store.pop('type')
        df = pd.DataFrame.from_dict([store])
        df['time'] = df.time.apply(dt.datetime.fromisoformat)
        df.set_index('time').to_sql(store_category, con=ENGINE, if_exists='append')
        app.server.logger.info(f'store data for {store}')
        return 'success', True

    @app.callback(
        Output({'index': category, 'type': 'debug'}, 'children'),
        Input({'index': category, 'type': 'store'}, 'data'),
        prevent_initial_call=True,
    )
    def on_update_store(store):
        return html.Pre(json.dumps(store, indent=2))

    @app.callback(
        Output({'index': category, 'type': 'table'}, 'data'),
        Output({'index': category, 'type': 'table'}, 'tooltip_data'),
        Input({'index': category, 'type': 'update'}, 'color'),
        prevent_initial_call=True,
    )
    def update_table2(_):
        triggered = ctx.triggered_prop_ids.values()
        triggered_category = next(iter(triggered)).get('index')
        try:
            df = pd.read_sql_table(triggered_category, con=ENGINE)\
                .sort_values(by='time', ascending=False)
        except ValueError as err:
            app.server.logger.critical(err)
            df = pd.DataFrame()

        def localize_timedelta_dir(time_delta):
            return bd.format_timedelta(
                time_delta,
                locale=LOCALE,
                granularity='minutes',
                add_direction=True,
            )
        now = dt.datetime.now().replace(tzinfo=None)
        delta = (df.time - now).map(localize_timedelta_dir)
        df.insert(1, 'delta', delta)

        def localize_timedelta(datetime):
            return bd.format_timedelta(
                datetime,
                locale=LOCALE,
                granularity='minutes'
            )
        age = (BIRTH_DATE - df.time).map(localize_timedelta)
        df.insert(2, 'age', age)

        check = generate_fa_icon('check')
        xmark = generate_fa_icon('xmark')

        boolean = df.columns[df.dtypes == bool]
        df[boolean] = df[boolean].replace(
            to_replace=[True, False],
            value=[check, xmark])
        data = df.to_dict('records')

        def localize_datetime(datetime):
            return bd.format_datetime(
                datetime,
                locale=LOCALE,
                format='medium',
            )
        tooltip = [{
            'delta': {
                'value': localize_datetime(index),
                'type': 'text',
            },
        } for index in df.set_index('time').age.index]

        return data, tooltip


@app.callback(
    Output('date-time', 'value'),
    Input('update-date-time', 'n_clicks'),
)
def update_datetime(_):
    return dt.datetime.now().isoformat(timespec='minutes')


@app.callback(
    Output({'index': 'pee-color', 'type': 'diaper'}, 'value'),
    Input({'index': 'pee', 'type': 'diaper'}, 'value'),
)
def update_last_pee_color(value):
    if not value:
        return dash.no_update
    df = pd.read_sql_table('diaper', con=ENGINE).set_index('time')
    color = df[df.pee]['pee-color'].dropna().sort_index().tail(1).iloc[0]
    return color


@app.callback(
    Output({'index': 'poo-color', 'type': 'diaper'}, 'value'),
    Input({'index': 'poo', 'type': 'diaper'}, 'value'),
)
def update_last_poo_color(value):
    if not value:
        return dash.no_update
    df = pd.read_sql_table('diaper', con=ENGINE).set_index('time')
    color = df[df.poo]['poo-color'].dropna().sort_index().tail(1).iloc[0]
    return color


@app.callback(
    Output({'index': 'diaper', 'type': 'table'}, 'style_data_conditional'),
    Input({'index': 'diaper', 'type': 'table'}, 'data'),
    State({'index': 'diaper', 'type': 'table'}, 'data_previous'),
)
def update_diaper_colors(data, data_last):
    if data == data_last:
        return dash.no_update
    styles = []
    df = pd.DataFrame.from_records(data)
    for color in df['pee-color'].unique():
        styles.append({
            'if': {
                'column_id': 'pee',
                'filter_query': f'{{pee-color}} = "{color}"',
            },
            'backgroundColor': color,
        })
    for color in df['poo-color'].unique():
        styles.append({
            'if': {
                'column_id': 'poo',
                'filter_query': f'{{poo-color}} = "{color}"',
            },
            'backgroundColor': color,
        })
    return styles


@app.callback(
    Output({'index': 'bilirubin', 'type': 'figure'}, 'children'),
    Input({'index': 'doctor', 'type': 'table'}, 'data'),
    State({'index': 'doctor', 'type': 'table'}, 'data_previous'),
)
def update_bilirubin_data(data, data_last):
    if data == data_last:
        return dash.no_update
    df = pd.DataFrame.from_records(data)
    df = df[df['bilirubin'].notna()]
    df['age'] = (df.time.apply(pd.Timestamp) - BIRTH_DATE).astype('timedelta64[h]')
    df = df.set_index('age')
    return generate_bilirubin_figure(data=df['bilirubin'])


if __name__ == '__main__':
    app.run_server(debug=True, host='0.0.0.0')
