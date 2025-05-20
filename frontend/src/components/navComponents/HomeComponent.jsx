import { AgGridReact } from "ag-grid-react";
import { useState, useMemo } from "react";
import Plot from "react-plotly.js";
import {
  AllCommunityModule,
  ModuleRegistry,
  colorSchemeDarkBlue,
  themeQuartz,
} from "ag-grid-community";
import {
  Box,
  Button,
  Divider,
  FormControl,
  TextField,
  Toolbar,
  Typography,
} from "@mui/material";

import Tab from "@mui/material/Tab";
import TabContext from "@mui/lab/TabContext";
import TabList from "@mui/lab/TabList";
import TabPanel from "@mui/lab/TabPanel";
import "../../css/navComponents/HomeComponent.css";

export const HomeComponent = () => {
  const [query, setQuery] = useState("");

  const intialRowData = [
    {
      "Order ID": 101,
      "Order Date": "2024-02-20",
      Price: 20.5,
      "Is Spicy": true,
      Category: "Fast Food",
      "Customer ID": 1,
    },
    {
      "Order ID": 102,
      "Order Date": "2024-02-21",
      Price: 15.0,
      "Is Spicy": false,
      Category: "Dessert",
      "Customer ID": 2,
    },
    {
      "Order ID": 103,
      "Order Date": "2024-02-22",
      Price: 30.0,
      "Is Spicy": true,
      Category: "Beverage",
      "Customer ID": 3,
    },
    {
      "Order ID": 104,
      "Order Date": "2024-02-23",
      Price: 25.0,
      "Is Spicy": false,
      Category: "Main Course",
      "Customer ID": 4,
    },
    {
      "Order ID": 105,
      "Order Date": "2024-02-24",
      Price: 18.5,
      "Is Spicy": true,
      Category: "Appetizer",
      "Customer ID": 5,
    },
    {
      "Order ID": 106,
      "Order Date": "2024-02-25",
      Price: 22.0,
      "Is Spicy": false,
      Category: "Fast Food",
      "Customer ID": 6,
    },
    {
      "Order ID": 107,
      "Order Date": "2024-02-26",
      Price: 27.5,
      "Is Spicy": true,
      Category: "Main Course",
      "Customer ID": 7,
    },
    {
      "Order ID": 108,
      "Order Date": "2024-02-28",
      Price: 24.5,
      "Is Spicy": true,
      Category: "Main Course",
      "Customer ID": 8,
    },
  ];
  const [rowData, setRowData] = useState(intialRowData);

  // Column Definitions: Defines the columns to be displayed.
  const [colDefs] = useState([
    { field: "Order ID", filter: "agNumberColumnFilter" },
    { field: "Order Date", filter: "agTextColumnFilter" },
    { field: "Price", filter: "agNumberColumnFilter", maxWidth: 100 },
    { field: "Is Spicy" },
    { field: "Category", filter: "agTextColumnFilter" },
    { field: "Customer ID", filter: "agNumberColumnFilter" },
  ]);

  const rowSelection = useMemo(() => {
    return {
      mode: "multiRow",
    };
  }, []);

  // Dropdown- Graph
  const [tabValue, setTabValue] = useState("1");
  const [graphType, setGraphType] = useState("bar");
  const [barMode, setBarMode] = useState(null);
  const [orientation, setOreintation] = useState("");
  const [mode, setMode] = useState("");
  const [fill, setFill] = useState("");
  const [selectValue, setSelectValue] = useState("scatter");

  // x-axis
  const [xaxisColumn, setXaxisColumn] = useState("Order ID");

  // y-axis
  const [yaxisColoumn, setYaxisColoumn] = useState("Customer ID");

  ModuleRegistry.registerModules([AllCommunityModule]);
  themeQuartz.withPart(colorSchemeDarkBlue);
  const myTheme = themeQuartz.withParams({
    // fontFamily: "serif",
    headerFontFamily: '"Headland One", serif',
    cellFontFamily: '"Headland One", serif',
  });

  const handleQuerySubmit = (e) => {
    e.preventDefault();
    if (!query) return setRowData(intialRowData);

    const lowerQuery = query.toLowerCase();
    setGraphType("bar");
    setBarMode("group");
    // setMode('lines+markers')
    setSelectValue("bar_group_coloumn");
    if (lowerQuery.includes("price")) {
      const resultQueryData = lowerQuery.includes("highest price")
        ? intialRowData.reduce(
            (max, current) => (current.Price > max.Price ? current : max),
            rowData[0]
          )
        : lowerQuery.includes("lowest price")
        ? intialRowData.reduce(
            (min, current) => (current.Price < min.Price ? current : min),
            rowData[0]
          )
        : intialRowData.map((x) => x.Price);

      if (Array.isArray(resultQueryData)) {
        setRowData(resultQueryData);
        setXaxisColumn("Category");
        setYaxisColoumn("Price");
      } else {
        setRowData([resultQueryData]);
        setXaxisColumn("Category");
        setYaxisColoumn("Price");
      }
    } else if (lowerQuery.includes("most used category")) {
      const categoryCounts = intialRowData.reduce((acc, current) => {
        acc[current.Category] = (acc[current.Category] || 0) + 1;
        return acc;
      }, {});

      const mostUsedCategory = Object.entries(categoryCounts).reduce(
        (max, current) => {
          return current[1] > max[1] ? current : max;
        }
      )[0];

      const mostUsedCategoryRecords = intialRowData.filter(
        (record) => record.Category === mostUsedCategory
      );

      if (Array.isArray(mostUsedCategoryRecords)) {
        setRowData(mostUsedCategoryRecords);
        setXaxisColumn("Category");
        setYaxisColoumn("Customer ID");
      } else {
        setRowData([mostUsedCategoryRecords]);
        setXaxisColumn("Category");
        setYaxisColoumn("Customer ID");
      }
    }
  };

  const handleTabListChange = (event, newValue) => {
    setTabValue(newValue);
  };

  const handleGraphTypeChange = (event) => {
    const selectedType = event.target.value;
    const extractGraphType = selectedType.split("_")[0];
    setSelectValue(selectedType);

    setGraphType(extractGraphType);

    if (extractGraphType === "bar") {
      const selectedBarMode =
        event.target.selectedOptions[0].getAttribute("data-barmode");
      const selectedOreintation =
        event.target.selectedOptions[0].getAttribute("data-orientation");
      setOreintation(selectedOreintation);
      setBarMode(selectedBarMode);
    } else if (extractGraphType === "scatter") {
      const selectedFill =
        event.target.selectedOptions[0].getAttribute("data-fill");
      const selectedMode =
        event.target.selectedOptions[0].getAttribute("data-mode");
      setFill(selectedFill);
      setMode(selectedMode);
    } else {
      setBarMode(null);
      setFill(null);
    }
  };

  return (
    <div className="homeComponent">
      <Box>
        <h1>Welcome to Gen AI!</h1>
      </Box>
      <Typography className="DescHome">
        Get started with this example project that uses SQL to find the most
        popular dessert order for a fictional dumpling restaurant.
      </Typography>

      <Box
        sx={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
        }}
      >
        <FormControl sx={{ width: "88%" }}>
          <TextField
            className="textFeildHome"
            placeholder="Ask a question"
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </FormControl>
        <Button
          variant="outlined"
          color="primary"
          className="submitButton"
          sx={{ verticalAlign: "middle" }}
          onClick={handleQuerySubmit}
        >
          Submit
        </Button>
      </Box>

      <Box sx={{ width: "100%", height: "20px", typography: "body1" }}>
        <TabContext value={tabValue}>
          <Box>
            <TabList
              indicatorColor="none"
              textColor="inherit"
              onChange={handleTabListChange}
              className="TabLsitHome"
            >
              <Tab
                sx={{ border: 1, borderColor: "divider" }}
                className="TabHome"
                label="Table"
                value="1"
              />
              <Tab
                sx={{ border: 1, borderColor: "divider" }}
                className="TabHome"
                label="Chart"
                value="2"
              />
            </TabList>
          </Box>

          <TabPanel className="TabPanelHome" value="1">
            <div
              style={{ height: "500px", width: "100%" }}
              className="parentOfAgGrid"
            >
              <AgGridReact
                className="ag-theme-quartz"
                theme={myTheme}
                rowSelection={rowSelection}
                rowData={rowData}
                columnDefs={colDefs}
              />
            </div>
          </TabPanel>

          <TabPanel
            className="TabPanelHome"
            value="2"
            sx={{ width: "100%", borderRadius: "10px" }}
          >
            <div
              style={{
                width: "100%",
                height: 460,
                border: "1px solid #dfdada",
              }}
            >
              <Box sx={{ display: "flex" }}>
                <Box
                  sx={{
                    width: "30%",
                    marginTop: "2%",
                    marginLeft: "1%",
                    minWidth: "300px",
                  }}
                >
                  <Box>
                    <label htmlFor="graphType">Type : </label>
                    <select
                      id="graphType"
                      value={selectValue}
                      onChange={handleGraphTypeChange}
                    >
                      <option
                        value="bar_group_coloumn"
                        data-barmode="group"
                        data-orientation=""
                      >
                        Grouped Coloumn
                      </option>
                      <option
                        value="bar_stacked_coloumn"
                        data-barmode="stack"
                        data-orientation=""
                      >
                        Stacked Coloumn
                      </option>
                      <Divider />
                      <option
                        value="scatter_multiple_line_chart"
                        data-fill=""
                        data-mode="lines+markers"
                      >
                        Line Chart
                      </option>
                      <option
                        value="scatter_area_line_chart"
                        data-fill="tozeroy"
                        data-mode="lines+markers"
                      >
                        Stacked Area
                      </option>
                      <option
                        value="scatter_markers_line_chart"
                        data-fill=""
                        data-mode="markers"
                      >
                        Scattered Plot
                      </option>
                      <Divider />
                      <option
                        value="bar_group"
                        data-barmode="group"
                        data-orientation="h"
                      >
                        Grouped Bar
                      </option>
                      <option
                        value="bar_stacked"
                        data-barmode="stack"
                        data-orientation="h"
                      >
                        Stacked Bar
                      </option>
                      <option value="histogram">Histogram Bar</option>
                      <Divider />
                      <option value="pie">Pie Chart</option>
                    </select>
                  </Box>

                  <Toolbar />
                  <FilterationForXAxis
                    rowData={rowData}
                    xaxisColumn={xaxisColumn}
                    setXaxisColumn={setXaxisColumn}
                  />

                  <Toolbar />

                  <FilterationForYAxis
                    rowData={rowData}
                    yaxisColoumn={yaxisColoumn}
                    setYaxisColoumn={setYaxisColoumn}
                  />
                </Box>

                <Box style={{ borderLeft: "1px solid #dfdada", width: "100%" }}>
                  {graphType === "histogram" && <HistogramComponent />}

                  {graphType === "pie" && <PieComponent />}

                  {graphType !== "histogram" && graphType !== "pie" && (
                    <Plot
                      data={getDynamicGraphData(
                        xaxisColumn,
                        yaxisColoumn,
                        rowData,
                        graphType,
                        orientation,
                        mode,
                        fill
                      )} // Dynamic data based on X and Y axis
                      layout={{
                        title: `Dynamic ${
                          graphType.charAt(0).toUpperCase() + graphType.slice(1)
                        } Graph`,
                        barmode: barMode,
                        xaxis: {
                          title: {
                            text: xaxisColumn,
                          },
                        },
                        yaxis: {
                          title: {
                            text: yaxisColoumn,
                          },
                        },
                      }}
                      config={{
                        responsive: true,
                      }}
                      style={{ width: "100%" }}
                    />
                  )}
                </Box>
              </Box>
            </div>
          </TabPanel>

          <Toolbar />
        </TabContext>
      </Box>
    </div>
  );
};

const getDynamicGraphData = (
  xaxisColumn,
  yaxisColoumn,
  rowData,
  graphType,
  orientation,
  mode,
  fill
) => {
  const xData = rowData.map((item) => item[xaxisColumn]);
  const yData = rowData.map((item) => item[yaxisColoumn]);

  const colors = [
    "#FF5733",
    "#33FF57",
    "#3357FF",
    "#F333FF",
    "#FF3356",
    "#FF8C00",
    "#00BFFF",
  ];
  const colorArray = rowData.map((_, index) => colors[index % colors.length]);

  return [
    {
      x: xData,
      y: yData,
      type: graphType,
      orientation: orientation,
      mode: mode,
      fill: fill,
      marker: {
        size: 12,
        color: colorArray,
      },
    },
  ];
};

const HistogramComponent = () => {
  const [dataHistogram] = useState([
    12, 14, 16, 18, 12, 20, 18, 17, 14, 19, 20, 22, 24, 18, 17, 14,
  ]);

  return (
    <Plot
      data={[
        {
          type: "histogram",
          x: dataHistogram,
          nbinsx: 10,
          name: "Sample Data",
          marker: {
            color: "rgba(50, 171, 96, 0.6)",
          },
        },
      ]}
      layout={{
        width: "100%",
        height: "100%",
        bargroupgap: 0.2,
        title: {
          text: "Sampled Results",
        },
        xaxis: {
          title: {
            text: "Value",
          },
        },
        yaxis: {
          title: {
            text: "Count",
          },
        },
      }}
    />
  );
};

const PieComponent = () => {
  return (
    <Plot
      data={[
        {
          type: "pie",
          labels: ["A", "B", "C"],
          values: [10, 20, 30],
          hoverinfo: "label+percent",
          // textinfo: 'label+percent',
        },
      ]}
      layout={{
        width: "100%",
        height: "100%",
        title: {
          text: "Pie Results",
        },
        showlegend: true,
      }}
    />
  );
};

const FilterationForXAxis = ({ rowData, xaxisColumn, setXaxisColumn }) => {
  return (
    <>
      <Box sx={{ mt: 2, display: "flex", alignItems: "baseline" }}>
        <label>X-axis : </label>
        <FilterationForAxis
          rowData={rowData}
          axisColumn={xaxisColumn}
          setAxisColumn={setXaxisColumn}
          axisType="x"
          SetScaleType={SetScaleTypeForX} // Pass X-axis scale type function
        />
      </Box>
    </>
  );
};

const FilterationForYAxis = ({ rowData, yaxisColoumn, setYaxisColoumn }) => {
  return (
    <>
      <Box sx={{ mt: 2, display: "flex", alignItems: "baseline" }}>
        <label>Y-axis : </label>
        <FilterationForAxis
          rowData={rowData}
          axisColumn={yaxisColoumn}
          setAxisColumn={setYaxisColoumn}
          axisType="y"
          SetScaleType={SetAggregateTypeForY} // Pass Y-axis scale type function
        />
      </Box>
    </>
  );
};

const FilterationForAxis = ({
  rowData,
  axisColumn,
  setAxisColumn,
  axisType,
  SetScaleType,
}) => {
  const columnTypes = {};
  if (rowData.length === 0) return null;

  Object.keys(rowData[0]).forEach((key) => {
    const value = rowData[0][key];
    if (typeof value === "number") {
      columnTypes[key] = "numeric";
    } else if (typeof value === "boolean") {
      columnTypes[key] = "boolean";
    } else if (!isNaN(Date.parse(value))) {
      columnTypes[key] = "datetime";
    } else {
      columnTypes[key] = "string";
    }
  });

  const handleAxisColumn = (e) => {
    setAxisColumn(e.target.value);
  };

  return (
    <Box className="axisDropdown">
      {/* Axis Column Selection */}
      <select
        id={`${axisType}-axisType`}
        onChange={handleAxisColumn}
        value={axisColumn}
        style={{ marginTop: "3%", width: "100%" }}
      >
        <option value="">Select a column</option>
        {Object.keys(columnTypes).map((colNames) => (
          <option key={colNames} value={colNames}>
            {colNames}
          </option>
        ))}
      </select>

      {/* Scale Type Selection */}
      {axisColumn && columnTypes[axisColumn] && (
        <Box id="scaleTypeParent">
          <Typography
            style={{
              marginRight: "10px",
              fontSize: "12px",
              fontFamily: 'Headland One", serif',
            }}
          >
            Scale Type
          </Typography>
          {/* <select id="scaleType"> */}
          <select id={`${axisType}-scaleType`}>
            {SetScaleType(columnTypes[axisColumn]).map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </Box>
      )}
    </Box>
  );
};

const SetScaleTypeForX = (type) => {
  switch (type) {
    case "numeric":
      return ["Number"];
    case "datetime":
      return ["Datetime"];
    case "string":
      return ["String"];
    case "boolean":
      return ["boolean"];
    default:
      return ["Default"];
  }
};

const SetAggregateTypeForY = (type) => {
  switch (type) {
    case "numeric":
      return ["Number", "String"];
    case "datetime":
      return ["Datetime", "String"];
    case "string":
      return ["String", "Datetime", "Number"];
    default:
      return ["Default"];
  }
};
