import { AppShell, Burger, Container, Group, Paper, Text } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import Logo from '../Logo/Logo';

interface AppLayoutProps {
  children: React.ReactNode;
}

export default function AppLayout({ children }: AppLayoutProps) {
  const [opened, { toggle }] = useDisclosure();

  return (
    <AppShell header={{ height: 70 }} padding="md">
      <AppShell.Header bg="sccGreen.9">
        <Group h="100%" px="md">
          {/* <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" /> */}
          <Logo />
          <Text c="white" fw={600}>
            Home To School Transport Eligibility Checker
          </Text>
        </Group>
      </AppShell.Header>
      <AppShell.Main>
        <Container fluid style={{ width: '100%', alignItems: 'stretch' }}>
          <Paper
            style={{ height: '100%', backgroundColor: 'var(--mantine-color-default)' }}
            shadow="md"
            radius="md"
            p="md"
          >
            {children}
          </Paper>
        </Container>
      </AppShell.Main>
    </AppShell>
  );
}
