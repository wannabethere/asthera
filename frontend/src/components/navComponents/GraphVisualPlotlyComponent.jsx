import Plot from 'react-plotly.js';

export const GraphVisualPlotly = ({ visualization }) => {

    console.log('Visualization data:', visualization);

    if (!visualization?.graphData) {
        return <div>No graph data available</div>;
    }

    const { graphType, graphData, label, responseType, component } = visualization;
    var graphDataLength = graphData.length;
    // console.log('graphdetials', graphType + '-->' + graphDataLength)

    const isGrouped = Array.isArray(graphData) && (graphData[0]?.values || graphData[0]?.value) && graphType === 'grouped bar';
    const isPie = Array.isArray(graphData) && graphData[0]?.value && graphType === 'pie';
    const isStacked = Array.isArray(graphData) && graphType === 'stacked bar';

    let data = [];

    if (isGrouped) {
        // const allSubLabels = [
        //     ...new Set(graphData.flatMap(group => group.values.map(val => val.label)
        //         || group.value.map(val => val.label)
        // ))
        // ];

        const allSubLabels = [
            ...new Set(
                graphData.flatMap(group => {
                    const values = group.values || group.value || [];
                    return values.map(val => val.label);
                })
            )
        ];

        data = allSubLabels.map((subLabel, idx) => {
            return {
                x: graphData.map(group => group.group),
                y: graphData.map(group => {
                    const subItem = group.values.find(v => v.label === subLabel);
                    return subItem ? subItem.value : 0;
                }),
                name: subLabel,
                type: 'bar',
                marker: {
                    color: ['#FF5733', '#33FF57', '#3357FF', '#F333FF', '#FF3356', '#FF8C00', '#00BFFF'][idx % 7],
                }
            };
        });
    } else if (isPie) {
        data = [{
            type: 'pie',
            values: graphData.map(item => item.value),
            labels: graphData.map(item => item.column),
            name: graphData[0]?.label || 'Net Value',
            marker: {
                colors: graphData.map((_, idx) =>
                    ['#FF5733', '#33FF57', '#3357FF', '#F333FF', '#FF3356', '#FF8C00', '#00BFFF'][idx % 7]
                )
            },
            textinfo: 'label+percent',
            hoverinfo: 'label+value',
        }];
    } else if (isStacked) {
        const allSubLabels = [
            ...new Set(graphData.flatMap(group => group.values.map(val => val.label)))
        ];

        data = allSubLabels.map((subLabel, idx) => {
            return {
                x: graphData.map(group => group.group),
                y: graphData.map(group => {
                    const subItem = group.values.find(v => v.label === subLabel);
                    return subItem ? subItem.value : 0;
                }),
                name: subLabel,
                type: 'bar',
                marker: {
                    color: ['#FF5733', '#33FF57', '#3357FF', '#F333FF', '#FF3356', '#FF8C00', '#00BFFF'][idx % 7],
                }
            };
        });
    } else {
        // Noraml bar chart
        data = [{
            type: graphType || 'bar',
            x: graphData.map(item => item.column || item.group),
            y: graphData.map(item => item.value),
            marker: {
                color: '#636efa'
            }
        }];
    }

    return (
        <Plot
            data={data}
            layout={{

                barmode: isGrouped ? 'group' : isStacked ? 'stack' : 'relative',
                xaxis: {
                    title: {
                        text: label || '',
                    }
                },
                yaxis: {
                    title: {
                        text: 'Value'
                    }
                },
                height: 400
            }}
            config={{
                responsive: true,
            }}
            style={{ width: component === 'collection' ? '100%' : graphDataLength > 5 ? '100%' : '50%' }}
        />
    );
};
