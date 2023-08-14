"""
A module for handling HTTP requests.
classes:
    RequestHandler: Class for handling HTTP requests and responses.
"""
import logging

import random
import time
from typing import Dict, Literal, Any, Optional

import requests
from requests.exceptions import HTTPError, Timeout, ReadTimeout

from ctk.exceptions import UnspecifiedHTTPStatusError


class RequestHandler:
    """
    RequestHandler: Class for handling HTTP requests to APIs. Includes exponential backoff feature
    and status code handling.
    """

    def __init__(self, base_url: str,
                 headers: Dict[str, Any] = None,
                 method: Literal['GET', 'POST'] = 'GET',
                 request_interval: int = 5,
                 retry_max_attempts: int = 3,
                 valid_statuses: set[int] = {200, 201},
                 invalid_statuses: set[int] = {
                     400, 401, 403, 404, 429, 500, 503},
                 retry_statuses: set[int] = {429}):
        """Constructor for RequestHandler.

        Args:
            base_url (str): The base url for the requests to be made to.
            headers (Dict[str, str], optional): Headers for API request. Defaults to None.
            method (Literal['GET', 'POST']): The request method to be used.
            request_interval (int): The interval in seconds that the handler should wait between requests.
            retry_max_attempts (int, optional): Maximum number of times the handler will retry 
            a given request. Defaults to 7.
            valid_statuses (set[int]): Set of valid status codes for API responses. These will 
            not be re-tried and the response will be returned. Defaults to {200, 201}.
            invalid_statuses (set[int]): Set of invalid status codes for API responses. 
            Defaults to {400, 401, 403, 404, 429, 500, 503}. Raises HTTPError, if response status is one of these.
            retry_statuses (set[int]): Set of invalid status codes, which trigger _backoff_delay() method.
            defaults to {429}.
        """
        self.base_url = base_url
        self.headers = headers
        self.method = method
        self.request_interval = request_interval
        self.retry_max_attempts = retry_max_attempts
        self.invalid_statuses = invalid_statuses
        self.valid_statuses = valid_statuses
        self.retry_statuses = retry_statuses

    @staticmethod
    def _backoff_delay(attempt_number: int) -> float:
        """_backoff_delay(int): Backoff delay method, to exponentially backoff requests
        which return responses with re-tryable invalid status codes.

        Args:
            attempt_number (int): The current number of retry attempts that have been made.

        Returns:
            float: The calculated backoff delay time in seconds.
        """
        logging.info('Calculating backoff delay...')
        delay = min(2 ** attempt_number, 10)
        jitter = random.uniform(0, 1)
        return delay * (1 + jitter)

    def _handle_response(self, response: requests.Response) -> bool:
        """_handle_response(requests.Response): Checks the status code of the HTTP response
        from the request made.

        Args:
            response (requests.Response): The response of the HTTP request.

        Raises:
            HTTPError: Erronious HTTP response.

        Returns:
            bool: The validity of the HTTP response.
        """
        logging.info('Checking response status...')
        logging.debug('Response status: %s', str(response.status_code))
        if response.status_code in self.valid_statuses:
            logging.info('Response is valid.')
            return True
        elif response.status_code in self.invalid_statuses:
            logging.info('Response is invalid.')
            raise HTTPError(response.content.decode('utf-8'))
        else:
            raise UnspecifiedHTTPStatusError(
                f'Response status code not specified as valid or invalid: {str(response.status_code)}')

    def handle_request(self,
                       post_data: Optional[Dict[str, Any]],
                       params: Dict[str, Any] = None) -> Dict[str, Any]:
        """The entry method of RequestHandler. Calls other methods to provide cohesive requests process.
        Args:
            post_data (Optional[Dict[str, Any]]): Data to post, when using 'POST' request method.
            params (Dict[str, Any], optional): Paramaters to make request with. Defaults to None.

        Raises:
            ValueError: If the self.method value is not 'GET' or 'POST'.
            e: If max retries is reached, and the response is still erroneous.

        Returns:
            Dict[str, Any]: The HTTP response of the request.
        """
        logging.info('Handling request...')
        logging.debug('Request paramaters: %s\nRequest data: %s',
                      str(params), str(post_data))

        attempt_number = 1
        while attempt_number <= self.retry_max_attempts:
            # Try to make HTTP request
            try:
                if self.method == 'GET':
                    logging.debug('Sending GET request...')
                    response = requests.get(
                        self.base_url, headers=self.headers, params=params, timeout=30)
                elif self.method == 'POST':
                    logging.debug('Sending POST request...')
                    response = requests.post(self.base_url,
                                             headers=self.headers,
                                             params=params,
                                             json=post_data,
                                             timeout=30)
                else:
                    raise ValueError(f'Invalid HTTP method: {self.method}')

                # If response is valid, return the response.json()
                if self._handle_response(response):
                    return response.json()
            # If a HTTPError, Timeout or ReadTimeout Exception is raised
            # retry, if the status code is a retry status and max attempts not reached
            except (HTTPError, Timeout, ReadTimeout) as e:
                logging.debug('Request error: %s', e)
                # Max attempts has been reached, or it is not a retry status
                # Reraise the exceptions
                if attempt_number == self.retry_max_attempts or response.status_code not in self.retry_statuses:
                    logging.info('Max retries reached.')
                    raise e
                logging.info('Resending request...')
                delay = self._backoff_delay(attempt_number)
                time.sleep(delay)
                attempt_number += 1
            except UnspecifiedHTTPStatusError as e:
                raise e
            finally:
                logging.info('Waiting request interval: %s',
                             str(self.request_interval))
                time.sleep(self.request_interval)
