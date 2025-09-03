import { createTheme, MantineColorsTuple } from '@mantine/core';

const sccGreen: MantineColorsTuple = [
  '#ebfffb',
  '#d6fdf6',
  '#a8fdec',
  '#79fde1',
  '#5afdd8',
  '#4cfdd3',
  '#43fdd0',
  '#37e1b7',
  '#014336',
  '#00604d'
];

export const theme = createTheme({
  colors: {
    sccGreen,
  }
});
