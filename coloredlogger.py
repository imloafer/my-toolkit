import logging

import coloredlogs


def coloredlogger(name):

    logger = logging.getLogger(name)

    fmt = "%(levelname)s [%(asctime)s] %(name)s - %(message)s"
    date_fmt = "%Y-%m-%d %H:%M:%S"
    level_styles = {'critical': {'bold': True, 'color': 'red'},
                    'debug': {'color': 'green'},
                    'error': {'color': 'red'},
                    'info': {'color': 'white'},
                    'warning': {'color': 'yellow'}}
    field_styles = {'asctime': {'color': 'green'},
                    'hostname': {'color': 'magenta'},
                    'levelname': {'bold': True, 'color': 'blue'},
                    'name': {'color': 'blue'},
                    'programname': {'color': 'cyan'},
                    'username': {'color': 'yellow'}}

    coloredlogs.install(level='DEBUG',
                        logger=logger,
                        fmt=fmt,
                        datefmt=date_fmt,
                        level_styles=level_styles,
                        field_styles=field_styles)
    return logger


if __name__ == '__main__':
    logger = coloredlogger(__name__)
    logger.debug("this is a debugging message")
    logger.info("this is an informational message")
    logger.warning("this is a warning message")
    logger.error("this is an error message")
    logger.critical("this is a critical message")

