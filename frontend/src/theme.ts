import { createTheme, MantineColorsTuple } from '@mantine/core';

const sccGreen: MantineColorsTuple = [
  '#014336',
  '#014336',
  '#014336',
  '#014336',
  '#014336',
  '#014336',
  '#014336',
  '#014336',
  '#014336',
  '#00604d'
];

const sccRed: MantineColorsTuple = [
  '#a60000',
  '#a60000',
  '#a60000',
  '#a60000',
  '#a60000',
  '#a60000',
  '#a60000',
  '#a60000',
  '#a60000',
  '#a60000'
]

export const theme = createTheme({
  colors: {
    sccGreen,
    sccRed
  }
});
