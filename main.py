from SimuLine.Simulation.pipeline import main as simulation
from SimuLine.Simulation.Config.config import BASE_CONFIG as CONFIG
# from SimuLine.Simulation.Config.config import BASE_LABELED_CONFIG as CONFIG  # if negative_inter_type is not "-", use this instead of BASE_CONFIG
from copy import deepcopy
import pandas as pd


def finalize_config(config):
    config = deepcopy(config)
    config['version'] = '{}_{}_{}'.format(config['experiment'], config['var'], config['run'])
    config['dataset'] = 'SimuLine_{}_{}_{}'.format(config['experiment'], config['var'], config['run'])
    return config


def build_config_from_excel_row(row, base_config=None):
    config = deepcopy(base_config or CONFIG)
    for attr, value in row.items():
        attr_name, attr_type = attr.split('@')
        if value == '-':  # pass "-" values which means no setting
            continue
        if attr_type == 'str':
            config[attr_name] = value
        elif attr_type == 'int':
            config[attr_name] = int(value)
        elif attr_type == 'float':
            config[attr_name] = float(value)
        else:
            raise Exception('BAD CONFIGURATION FILE !!!')
    return finalize_config(config)


def load_batch_configs(path='./Config/Batch.xlsx'):
    experiment_settings = pd.read_excel(path)
    return [
        build_config_from_excel_row(experiment_settings.iloc[i])
        for i in range(experiment_settings.shape[0])
    ]


def run_simulation(config):
    prepared_config = finalize_config(config)
    simulation(prepared_config)
    return prepared_config


def main():
    for config in load_batch_configs():
        run_simulation(config)


if __name__ == "__main__":
    main()
