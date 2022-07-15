#  vim: set ts=4 sw=4 tw=0 et :
"""Baby tracker
"""

import datetime as dt
import dash
from dash import html, dcc, Input, Output, ALL, ctx
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import json
from sqlalchemy import create_engine

import configparser
import pathlib
import os.path


PROJECT_DIR = pathlib.Path(__file__).resolve().parents[1]
DATA_DIR = os.path.join(PROJECT_DIR, 'data')

config = configparser.ConfigParser()
config.read(os.path.join(DATA_DIR, 'config.ini'))

SERVER_TZ = dt.datetime.utcnow().astimezone().tzinfo
BIRTH_DATE = dt.datetime.fromisoformat(config['baby']['birth']).astimezone(SERVER_TZ).replace(tzinfo=None)
NAME = config['baby']['name']
LOCALE = config['settings'].get('locale', 'de_DE')
ENGINE = create_engine(f'sqlite:////{DATA_DIR}/{config["settings"]["database"]}')

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


def get_bilirubin_figure():
    """
    Factor: 1mg/dl = 17.1µmol/l
    Source: https://www.gastro.medline.ch/Services/_Tools/Um_und_Berechnungen/Umrechnung_von_mg_dl_mol_l.php
    """
    df = pd.DataFrame.from_dict(HYPERBILIRUBINEMIA, orient='tight').multiply(17.1)
    color_map = {
        '40th': px.colors.qualitative.Plotly[2],
        '75th': px.colors.qualitative.Plotly[0],
        '95th': px.colors.qualitative.Plotly[1],
    }
    pio = px.area(
        df,
        color_discrete_map=color_map,
        template='none',
        labels={'age': 'Alter [h]'},
        markers=True,
    ).update_layout(
        yaxis={'title': 'Bilirubin [µmol/l]'}
    )
    return dcc.Graph(figure=pio)


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
                        dbc.Card(id={'index': 'drink', 'type': 'table'}),
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
                        dbc.Card(id={'index': 'diaper', 'type': 'table'}),
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
                        dbc.Card(id={'index': 'pump', 'type': 'table'}),
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
                        html.Div(id={'index': 'doctor', 'type': 'debug'}, className='row visually-hidden'),
                        dbc.Card(id={'index': 'doctor', 'type': 'table'}),
                        dbc.Card([
                            dbc.CardBody(get_bilirubin_figure()),
                            dbc.CardFooter(
                                dcc.Link(
                                    'Bhutani et al. Pediatrics. 1999 Jan;103(1):6-14',
                                    href='https://doi.org/10.1542/peds.103.1.6',
                                    target='_blank',
                                )
                            )
                        ]),
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
        category = store.pop('type')
        df = pd.DataFrame.from_dict([store])
        df['time'] = df.time.apply(dt.datetime.fromisoformat)
        df.set_index('time').to_sql(category, con=ENGINE, if_exists='append')
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
        Output({'index': category, 'type': 'table'}, 'children'),
        Input({'index': category, 'type': 'update'}, 'color'),
        prevent_initial_call=True,
    )
    def on_update_database(_):
        triggered = ctx.triggered_prop_ids.values()
        category = next(iter(triggered)).get('index')
        try:
            df = pd.read_sql_table(category, con=ENGINE).sort_values(by='time').tail()
            df['time'] = (df.time - BIRTH_DATE)\
                .dt.round(dt.timedelta(minutes=1))\
                .astype(str).str.removesuffix(':00')
        except ValueError as err:
            app.server.logger.critical(err)
            df = pd.DataFrame()
        # work around for wrong display of boolean in React
        boolean = df.columns[df.dtypes == bool]
        df[boolean] = df[boolean].replace(to_replace=[True, False], value=['\u2713', '\u274C'])
        table = dbc.Table.from_dataframe(  # pylint: disable=E1101
            df.tail().iloc[::-1],
            striped=True,
            bordered=True,
            hover=True
        ),
        return table


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


if __name__ == '__main__':
    app.run_server(debug=True, host='0.0.0.0')
