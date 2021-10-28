"""Set up object oriented structure for Google Sheet data retrieval."""
# FIXME: ensure typechecking in the module

import json
import pathlib
import pickle
from typing import List, Dict
import yaml

import pandas as pd  # type: ignore[import]


from googleapiclient.discovery import build  # type: ignore[import]

from google.oauth2 import service_account  # type: ignore[import]

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class SheetCollector:
    """Authenticate Sheets api and store retrieved data."""

    def __init__(
        self, key_file="private/keys.json", sources_dir="config/sheet_sources"
    ) -> None:
        """
        Create a SheetCollector object that stores a dictionary of sheets.

        Uses the yaml files in the config/sheet_sources directory.

        Args:
            key_file (str, optional): path to Google Sheets API user keys and
            tokens. Defaults to "private/keys.json".
        """
        self.key_file: str = key_file
        (
            self.credentials,
            self.service,
            self.sheets,
        ) = SheetCollector.authenticate_api(self.key_file)
        self.config_dir = pathlib.Path(sources_dir)
        self.sheets_data: Dict[str, Sheet] = {}

    def print_contents(self) -> None:
        """Print all Sheet objects in self.sheets_data."""
        for _, sheet in self.sheets_data.items():
            sheet.print_sheet()

    def collect_files(self) -> None:
        """
        Update sheets_data with Sheet objects from Google Sheets.

        Requires that the API was authenticated successfully.

        Raises:
            Exception: thrown when the Google Sheets API is not authenticated.
        """
        if not self.sheets:
            raise Exception("ERROR: Collector was not authenticated")
        # get a list of all yaml path objects in the config_dir
        config_files = SheetCollector.get_yaml_files(self.config_dir)
        for yaml_file in config_files:
            # Open yaml file as read
            with open(yaml_file, "r", encoding="utf-8") as config_file:
                config_data = yaml.safe_load(config_file)
                # create sheet object using the yaml data
                sheet_obj = Sheet(config_data, self.sheets)
                # fill the sheet object with the regions
                # by excecuting API calls
                sheet_obj.collect_regions()
                # store the sheet object in sheet_data, use the yaml file name
                # as key
                self.sheets_data[yaml_file.stem] = sheet_obj

    @staticmethod
    def get_yaml_files(directory: pathlib.Path):
        """
        Find all yaml files recursively in directory.

        Args:
            directory (pathlib.Path): directory to search in

        Returns:
            list of path objects: paths to all found yaml files
        """
        return directory.glob("*.yaml")

    @staticmethod
    def authenticate_api(key_file):
        """Use credentials from key_file to authenticate access to a service account.

        Args:
            key_file (str, optional): Path to file containing API tokens.
                Defaults to "private/keys.json".
        """
        # TODO: add try statement for possible API errors
        credentials = service_account.Credentials.from_service_account_file(
            key_file, scopes=SCOPES
        )
        service = build("sheets", "v4", credentials=credentials)
        sheets = service.spreadsheets()
        return credentials, service, sheets


class Sheet:
    """Retrieve Google Sheets data and store as Regions."""

    def __init__(self, config: Dict, sheets_api) -> None:
        """Initialize a Sheet object.

        Args:
            config (Dict): a dictionary containing file
                sheets file retrieval configuration
            sheets_api: authenticated sheets api object
        """
        self.api = sheets_api
        self.config: Dict = config
        Sheet.check_config_schema(self.config)
        self.regions: Dict[str, Region] = {}

    def collect_regions(self):
        """Iterate through configuration and request data through API."""
        for sheet in self.config["sheets"]:
            for region in sheet["regions"]:
                region_data = Sheet.execute_sheets_call(
                    self.api,
                    self.config["source_id"],
                    sheet["name"],
                    region["start"],
                    region["end"],
                )
                # TODO: might need fixed
                if region["contains_headers"]:
                    data = Sheet.to_dataframe(region_data)
                else:
                    data = Sheet.to_dataframe(
                        region_data,
                        headers_in_data=False,
                        headers=region["headers"],
                    )
                region_object = Region(
                    region["name"],
                    sheet["name"],
                    region["start"],
                    region["end"],
                    data,
                )
                # FIXME: region naming discrepency
                self.regions[region["name"]] = region_object

    def get_region(self, region_name: str):
        """Return a region object from the regions dictionary.

        Args:
            region_name (str): name of the region to get

        Returns:
            Region: the region object from the self.regions dictionary
        """
        requested_region: Region = self.regions[region_name]
        return requested_region

    def print_sheet(self):
        """Iterate through self.regions and print the contents."""
        for region_id, region in self.regions.items():
            print(f"******\t {region_id} \t ******")
            region.print_region()
            print("*********************************")

    @staticmethod
    def to_dataframe(
        data: List[List], headers_in_data=True, headers=None
    ) -> pd.DataFrame:
        """Convert the data from Sheets API from List[List] pandas dataframe.

        Args:
            data (List[List]): Retrieved data from Sheets API
            headers_in_data (bool, optional): Is column headers included in the
                data. Defaults to True.
            headers (list, optional): If column headers are not included, use
            the headers in this list. Defaults to [].

        Raises:
            Exception: thrown when headers is empty and headers_in_data
            is False

        Returns:
            pd.DataFrame: The pandas dataframe after resulting from the data
        """
        if headers_in_data:
            # FIXME: possible indexing error here
            return pd.DataFrame(data[1:], columns=data[0])
        if not headers:
            raise Exception("No passed table headers")
        return pd.DataFrame(data, columns=headers)

    @staticmethod
    def check_config_schema(config: Dict):
        """Validate the yaml configuration against a preset schema.add().

        Args:
            config (Dict): the configuration to validate

        Raises:
            Exception: The schema doesn't validate agains the preset
            json schema
        """
        assert type(config) == dict
        # TODO: implement me
        # TODO: should throw an error if format not accurate
        # Don't do anything if it's accurate
        return True

    @staticmethod
    def execute_sheets_call(
        api, file_id: str, sheet_name: str, start_range: str, end_range: str
    ) -> list[list]:
        """Execute an API call to get google sheets data.

        Args:
            file_id (str): ID of the Google Sheet file
            sheet_name (str): Name of the sheet in the file
            start_range (str): Cell name to start from (eg. A4)
            end_range (str): Cell name to end at (eg. H5)

        Returns:
            list[list]: the data in the specified range.
        """
        # TODO: add try statement for API errors
        return (
            api.values()
            .get(
                spreadsheetId=file_id,
                range=f"{sheet_name}!{start_range}:{end_range}",
            )
            .execute()
            .get("values", [])
        )


class Region:
    """Store data frame and metadata about Google Sheet region."""

    def __init__(
        self,
        region_name: str,
        parent_sheet_name: str,
        start_range: str,
        end_range: str,
        data: pd.DataFrame,
    ) -> None:
        """Create a Region object.

        Args:
            region_name (str): name of the region
            parent_sheet_name (str): name of the sheet the region belongs to
            start_range (str): Cell name to start from (eg. A4)
            end_range (str): Cell name to end at (eg. H5)
            data (pd.DataFrame): Data in the region
        """
        self.region_name = region_name
        self.parent_sheet_name = parent_sheet_name
        self.full_name = f"{parent_sheet_name}_{region_name}"
        self.start_range = start_range
        self.end_range = end_range
        self.data = data

    def print_region(self):
        """Print the contents of the region in a markdown table format."""
        print(f"start range: {self.start_range}")
        print(f"end range: {self.end_range}")
        print(self.data.to_markdown())

    def region_to_pickle(self, directory: pathlib.PosixPath):
        """Write the region object to a Pickle file.

        Args:
            directory (pathlib.PosixPath): path to the directory where the file
                be stored
        """
        with open(
            pathlib.Path(".") / directory / f"{self.full_name}.pkl", "wb"
        ) as outfile:
            pickle.dump(self, outfile)

    def region_to_json(self, directory: pathlib.PosixPath):
        """Write the region object to a JSON file.

        Args:
            directory (pathlib.PosixPath): path to the directory where the file
                be stored
        """
        self_data = {
            "region_name": self.region_name,
            "parent_name": self.parent_sheet_name,
            "full_name": self.full_name,
            "start_range": self.start_range,
            "end_range": self.end_range,
            # TODO: determine the based format to store the data
            "data": self.data.to_dict("index"),
        }
        with open(
            pathlib.Path(".") / directory / f"{self.full_name}.json",
            "w+",
            encoding="utf-8",
        ) as outfile:
            json.dump(self_data, outfile, indent=4)
