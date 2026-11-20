import React from 'react';
import { Box, Typography, useTheme, SxProps, Theme } from '@mui/material';

export const DIAGPRO_SLOGAN = 'Concursos mais organizados. Resultados com precisão.';

export interface DiagProIconProps {
  size?: number;
  color?: string;
  monochrome?: boolean;
  roundedFrame?: boolean;
  sx?: SxProps<Theme>;
}

/**
 * Ícone oficial DiagPro: documento com canto dobrado, três linhas internas e checkmark na base.
 */
export const DiagProIcon: React.FC<DiagProIconProps> = ({
  size = 32,
  color,
  monochrome = false,
  roundedFrame = false,
  sx,
}) => {
  const theme = useTheme();
  const isLight = theme.palette.mode === 'light';
  const strokeColor =
    color || (monochrome ? '#FFFFFF' : isLight ? '#00A8D6' : '#00B4D8');

  return (
    <Box
      component="svg"
      viewBox="0 0 64 64"
      fill="none"
      aria-label="DiagPro"
      sx={{
        width: size,
        height: size,
        display: 'block',
        flexShrink: 0,
        filter: monochrome
          ? 'none'
          : isLight
            ? 'none'
            : 'drop-shadow(0 0 10px rgba(0, 180, 216, 0.35))',
        ...sx,
      }}
    >
      {roundedFrame ? (
        <rect
          x="10"
          y="7"
          width="44"
          height="50"
          rx="8"
          stroke={strokeColor}
          strokeWidth="4.4"
        />
      ) : (
        <>
          <path
            d="M13 6H39L53 20V54C53 55.1046 52.1046 56 51 56H13C11.8954 56 11 55.1046 11 54V8C11 6.89543 11.8954 6 13 6Z"
            stroke={strokeColor}
            strokeWidth="4.4"
            strokeLinejoin="round"
          />
          <path
            d="M39 6V20H53"
            stroke={strokeColor}
            strokeWidth="4"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </>
      )}
      <path
        d="M20.5 23.5H36.5M20.5 31H40.5M20.5 38.5H33.5"
        stroke={strokeColor}
        strokeWidth="4.2"
        strokeLinecap="round"
      />
      <path
        d="M15 45.5L25.5 55.5L47.5 33.5"
        stroke={strokeColor}
        strokeWidth="5.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Box>
  );
};

export interface DiagProLogoProps {
  variant?: 'horizontal' | 'stacked' | 'compact';
  showSlogan?: boolean;
  sloganText?: string;
  tone?: 'auto' | 'dark' | 'light' | 'white';
  iconSize?: number;
  sx?: SxProps<Theme>;
}

/**
 * Lockup oficial da marca DiagPro com tipografia bicolor ("Diag" + "Pro") e slogan.
 */
export const DiagProLogo: React.FC<DiagProLogoProps> = ({
  variant = 'horizontal',
  showSlogan = false,
  sloganText = DIAGPRO_SLOGAN,
  tone = 'auto',
  iconSize,
  sx,
}) => {
  const theme = useTheme();
  const resolvedTone =
    tone === 'auto' ? (theme.palette.mode === 'light' ? 'light' : 'dark') : tone;

  const diagColor =
    resolvedTone === 'white'
      ? '#FFFFFF'
      : resolvedTone === 'light'
        ? '#082548'
        : '#F8FAFC';

  const proColor =
    resolvedTone === 'white'
      ? '#FFFFFF'
      : resolvedTone === 'light'
        ? '#0072CE'
        : '#0EA5E9';

  const iconColor =
    resolvedTone === 'white'
      ? '#FFFFFF'
      : resolvedTone === 'light'
        ? '#00A8D6'
        : '#22D3EE';

  const sloganColor =
    resolvedTone === 'white'
      ? 'rgba(255, 255, 255, 0.78)'
      : resolvedTone === 'light'
        ? '#5B6779'
        : '#94A3B8';

  const resolvedIconSize =
    iconSize ?? (variant === 'stacked' ? 58 : variant === 'compact' ? 30 : 42);

  const fontSize =
    variant === 'stacked'
      ? '2rem'
      : variant === 'compact'
        ? '1.22rem'
        : '1.65rem';

  if (variant === 'stacked') {
    return (
      <Box
        sx={{
          display: 'inline-flex',
          flexDirection: 'column',
          alignItems: 'center',
          textAlign: 'center',
          gap: 1.25,
          ...sx,
        }}
      >
        <DiagProIcon
          size={resolvedIconSize}
          color={iconColor}
          monochrome={resolvedTone === 'white'}
        />
        <Box>
          <Typography
            component="div"
            sx={{
              fontWeight: 800,
              fontSize,
              lineHeight: 1.05,
              letterSpacing: '-0.025em',
            }}
          >
            <Box component="span" sx={{ color: diagColor }}>
              Diag
            </Box>
            <Box component="span" sx={{ color: proColor }}>
              Pro
            </Box>
          </Typography>
          {showSlogan && (
            <Typography
              sx={{
                fontSize: '0.78rem',
                fontWeight: 500,
                color: sloganColor,
                mt: 0.75,
                lineHeight: 1.35,
              }}
            >
              {sloganText}
            </Typography>
          )}
        </Box>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: variant === 'compact' ? 1.25 : 1.75,
        minWidth: 0,
        ...sx,
      }}
    >
      <DiagProIcon
        size={resolvedIconSize}
        color={iconColor}
        monochrome={resolvedTone === 'white'}
      />
      <Box sx={{ minWidth: 0 }}>
        <Typography
          component="div"
          sx={{
            fontWeight: 800,
            fontSize,
            lineHeight: 1.05,
            letterSpacing: '-0.025em',
          }}
        >
          <Box component="span" sx={{ color: diagColor }}>
            Diag
          </Box>
          <Box component="span" sx={{ color: proColor }}>
            Pro
          </Box>
        </Typography>
        {showSlogan && (
          <Typography
            noWrap={variant === 'compact'}
            sx={{
              fontSize: variant === 'compact' ? '0.68rem' : '0.76rem',
              fontWeight: 500,
              color: sloganColor,
              mt: 0.35,
              lineHeight: 1.25,
            }}
          >
            {sloganText}
          </Typography>
        )}
      </Box>
    </Box>
  );
};

export default DiagProLogo;
