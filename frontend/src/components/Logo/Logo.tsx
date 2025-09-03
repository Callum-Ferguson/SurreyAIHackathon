import { Image } from '@mantine/core';
import logoSvg from '@/images/surrey-county-council.svg';

export default function Logo() {
  return (
    <Image
      src={logoSvg}
      alt="Home To School Transport Eligibility Checker"
      width={50}
      height={50}
    />
  );
}
