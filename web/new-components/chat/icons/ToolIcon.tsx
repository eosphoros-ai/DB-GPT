import classNames from 'classnames';
import React from 'react';

// OpenCode-style SVG icons (20x20 viewBox)
const icons: Record<string, string> = {
  // Reading/viewing
  glasses: `<path d="M0.416626 7.91667H1.66663M19.5833 7.91667H18.3333M11.866 7.57987C11.3165 7.26398 10.6793 7.08333 9.99996 7.08333C9.32061 7.08333 8.68344 7.26398 8.13389 7.57987M8.74996 10C8.74996 12.0711 7.07103 13.75 4.99996 13.75C2.92889 13.75 1.24996 12.0711 1.24996 10C1.24996 7.92893 2.92889 6.25 4.99996 6.25C7.07103 6.25 8.74996 7.92893 8.74996 10ZM18.75 10C18.75 12.0711 17.071 13.75 15 13.75C12.9289 13.75 11.25 12.0711 11.25 10C11.25 7.92893 12.9289 6.25 15 6.25C17.071 6.25 18.75 7.92893 18.75 10Z" stroke="currentColor" stroke-linecap="square"/>`,

  // Console/bash
  console: `<path d="M3.75 5.4165L8.33333 9.99984L3.75 14.5832M10.4167 14.5832H16.25" stroke="currentColor" stroke-linecap="square"/>`,

  // Code/edit
  'code-lines': `<path d="M2.08325 3.75H11.2499M14.5833 3.75H17.9166M2.08325 10L7.08325 10M10.4166 10L17.9166 10M2.08325 16.25L8.74992 16.25M12.0833 16.25L17.9166 16.25" stroke="currentColor" stroke-linecap="square" stroke-linejoin="round"/>`,

  // List
  'bullet-list': `<path d="M9.58329 13.7497H17.0833M9.58329 6.24967H17.0833M6.24996 6.24967C6.24996 7.17015 5.50377 7.91634 4.58329 7.91634C3.66282 7.91634 2.91663 7.17015 2.91663 6.24967C2.91663 5.3292 3.66282 4.58301 4.58329 4.58301C5.50377 4.58301 6.24996 5.3292 6.24996 6.24967ZM6.24996 13.7497C6.24996 14.6701 5.50377 15.4163 4.58329 15.4163C3.66282 15.4163 2.91663 14.6701 2.91663 13.7497C2.91663 12.8292 3.66282 12.083 4.58329 12.083C5.50377 12.083 6.24996 12.8292 6.24996 13.7497Z" stroke="currentColor" stroke-linecap="square"/>`,

  // Search/magnifying glass
  'magnifying-glass': `<path d="M15.8332 15.8337L13.0819 13.0824M14.6143 9.39088C14.6143 12.2759 12.2755 14.6148 9.39039 14.6148C6.50532 14.6148 4.1665 12.2759 4.1665 9.39088C4.1665 6.5058 6.50532 4.16699 9.39039 4.16699C12.2755 4.16699 14.6143 6.5058 14.6143 9.39088Z" stroke="currentColor" stroke-linecap="square"/>`,

  // Search with menu
  'magnifying-glass-menu': `<path d="M2.08325 10.0002H4.58325M2.08325 5.41683H5.41659M2.08325 14.5835H5.41659M16.4583 13.9585L18.7499 16.2502M17.9166 10.0002C17.9166 12.9917 15.4915 15.4168 12.4999 15.4168C9.50838 15.4168 7.08325 12.9917 7.08325 10.0002C7.08325 7.00862 9.50838 4.5835 12.4999 4.5835C15.4915 4.5835 17.9166 7.00862 17.9166 10.0002Z" stroke="currentColor" stroke-linecap="square"/>`,

  // Task/delegation
  task: `<path d="M9.99992 2.0835V17.9168M7.08325 3.75016H2.08325V16.2502H7.08325M12.9166 16.2502H17.9166V3.75016H12.9166" stroke="currentColor" stroke-linecap="square"/>`,

  // Checklist/todo
  checklist: `<path d="M9.58342 13.7498H17.0834M9.58342 6.24984H17.0834M2.91675 6.6665L4.58341 7.9165L7.08341 4.1665M2.91675 14.1665L4.58341 15.4165L7.08341 11.6665" stroke="currentColor" stroke-linecap="square"/>`,

  // Web/cursor
  'window-cursor': `<path d="M17.9166 10.4167V3.75H2.08325V17.0833H10.4166M17.9166 13.5897L11.6666 11.6667L13.5897 17.9167L15.032 15.0321L17.9166 13.5897Z" stroke="currentColor" stroke-width="1.07143" stroke-linecap="square"/><path d="M5.00024 6.125C5.29925 6.12518 5.54126 6.36795 5.54126 6.66699C5.54108 6.96589 5.29914 7.20783 5.00024 7.20801C4.7012 7.20801 4.45843 6.966 4.45825 6.66699C4.45825 6.36784 4.70109 6.125 5.00024 6.125ZM7.91626 6.125C8.21541 6.125 8.45825 6.36784 8.45825 6.66699C8.45808 6.966 8.21531 7.20801 7.91626 7.20801C7.61736 7.20783 7.37542 6.96589 7.37524 6.66699C7.37524 6.36795 7.61726 6.12518 7.91626 6.125ZM10.8333 6.125C11.1324 6.125 11.3752 6.36784 11.3752 6.66699C11.3751 6.966 11.1323 7.20801 10.8333 7.20801C10.5342 7.20801 10.2914 6.966 10.2913 6.66699C10.2913 6.36784 10.5341 6.125 10.8333 6.125Z" fill="currentColor" stroke="currentColor" stroke-width="0.25" stroke-linecap="square"/>`,

  // MCP/generic tool
  mcp: `<g><path d="M0.972656 9.37176L9.5214 1.60019C10.7018 0.527151 12.6155 0.527151 13.7957 1.60019C14.9761 2.67321 14.9761 4.41295 13.7957 5.48599L7.3397 11.3552" stroke="currentColor" stroke-linecap="round"/><path d="M7.42871 11.2747L13.7957 5.48643C14.9761 4.41338 16.8898 4.41338 18.0702 5.48643L18.1147 5.52688C19.2951 6.59993 19.2951 8.33966 18.1147 9.4127L10.3831 16.4414C9.98966 16.7991 9.98966 17.379 10.3831 17.7366L11.9707 19.1799" stroke="currentColor" stroke-linecap="round"/><path d="M11.6587 3.54346L5.33619 9.29119C4.15584 10.3642 4.15584 12.1039 5.33619 13.177C6.51649 14.25 8.43019 14.25 9.61054 13.177L15.9331 7.42923" stroke="currentColor" stroke-linecap="round"/></g>`,

  // Question/chat bubble
  'bubble-5': `<path d="M18.3327 9.99935C18.3327 5.57227 15.0919 2.91602 9.99935 2.91602C4.90676 2.91602 1.66602 5.57227 1.66602 9.99935C1.66602 11.1487 2.45505 13.1006 2.57637 13.3939C2.58707 13.4197 2.59766 13.4434 2.60729 13.4697C2.69121 13.6987 3.04209 14.9354 1.66602 16.7674C3.51787 17.6528 5.48453 16.1973 5.48453 16.1973C6.84518 16.9193 8.46417 17.0827 9.99935 17.0827C15.0919 17.0827 18.3327 14.4264 18.3327 9.99935Z" stroke="currentColor" stroke-linecap="square"/>`,

  // Chevrons
  'chevron-down': `<path d="M6.6665 8.33325L9.99984 11.6666L13.3332 8.33325" stroke="currentColor" stroke-linecap="square"/>`,
  'chevron-right': `<path d="M8.33301 13.3327L11.6663 9.99935L8.33301 6.66602" stroke="currentColor" stroke-linecap="square"/>`,
  'chevron-grabber-vertical': `<path d="M6.66675 12.4998L10.0001 15.8332L13.3334 12.4998M6.66675 7.49984L10.0001 4.1665L13.3334 7.49984" stroke="currentColor" stroke-linecap="square"/>`,

  // Check marks
  check: `<path d="M5 11.9657L8.37838 14.7529L15 5.83398" stroke="currentColor" stroke-linecap="square"/>`,
  'check-small': `<path d="M6.5 11.4412L8.97059 13.5L13.5 6.5" stroke="currentColor" stroke-linecap="square"/>`,
  'circle-check': `<path d="M12.4987 7.91732L8.7487 12.5007L7.08203 10.834M17.9154 10.0007C17.9154 14.3729 14.371 17.9173 9.9987 17.9173C5.62644 17.9173 2.08203 14.3729 2.08203 10.0007C2.08203 5.6284 5.62644 2.08398 9.9987 2.08398C14.371 2.08398 17.9154 5.6284 17.9154 10.0007Z" stroke="currentColor" stroke-linecap="square"/>`,

  // Close/X
  close: `<path d="M3.75 3.75L16.25 16.25M16.25 3.75L3.75 16.25" stroke="currentColor" stroke-linecap="square"/>`,
  'circle-x': `<path fill-rule="evenodd" clip-rule="evenodd" d="M1.6665 10.0003C1.6665 5.39795 5.39746 1.66699 9.99984 1.66699C14.6022 1.66699 18.3332 5.39795 18.3332 10.0003C18.3332 14.6027 14.6022 18.3337 9.99984 18.3337C5.39746 18.3337 1.6665 14.6027 1.6665 10.0003ZM7.49984 6.91107L6.91058 7.50033L9.41058 10.0003L6.91058 12.5003L7.49984 13.0896L9.99984 10.5896L12.4998 13.0896L13.0891 12.5003L10.5891 10.0003L13.0891 7.50033L12.4998 6.91107L9.99984 9.41107L7.49984 6.91107Z" fill="currentColor"/>`,

  // Folder
  folder: `<path d="M2.08301 2.91675V16.2501H17.9163V5.41675H9.99967L8.33301 2.91675H2.08301Z" stroke="currentColor" stroke-linecap="round"/>`,
  'folder-add-left': `<path d="M2.08333 9.58268V2.91602H8.33333L10 5.41602H17.9167V16.2493H8.75M3.75 12.0827V14.5827M3.75 14.5827V17.0827M3.75 14.5827H1.25M3.75 14.5827H6.25" stroke="currentColor" stroke-linecap="square"/>`,

  // Edit
  edit: `<path d="M17.0832 17.0807V17.5807H17.5832V17.0807H17.0832ZM2.9165 17.0807H2.4165V17.5807H2.9165V17.0807ZM2.9165 2.91406V2.41406H2.4165V2.91406H2.9165ZM9.58317 3.41406H10.0832V2.41406H9.58317V2.91406V3.41406ZM17.5832 10.4141V9.91406H16.5832V10.4141H17.0832H17.5832ZM6.24984 11.2474L5.89628 10.8938L5.74984 11.0403V11.2474H6.24984ZM6.24984 13.7474H5.74984V14.2474H6.24984V13.7474ZM8.74984 13.7474V14.2474H8.95694L9.10339 14.101L8.74984 13.7474ZM15.2082 2.28906L15.5617 1.93551L15.2082 1.58196L14.8546 1.93551L15.2082 2.28906ZM17.7082 4.78906L18.0617 5.14262L18.4153 4.78906L18.0617 4.43551L17.7082 4.78906ZM17.0832 17.0807V16.5807H2.9165V17.0807V17.5807H17.0832V17.0807ZM2.9165 17.0807H3.4165V2.91406H2.9165H2.4165V17.0807H2.9165ZM2.9165 2.91406V3.41406H9.58317V2.91406V2.41406H2.9165V2.91406ZM17.0832 10.4141H16.5832V17.0807H17.0832H17.5832V10.4141H17.0832ZM6.24984 11.2474H5.74984V13.7474H6.24984H6.74984V11.2474H6.24984ZM6.24984 13.7474V14.2474H8.74984V13.7474V13.2474H6.24984V13.7474ZM6.24984 11.2474L6.60339 11.6009L15.5617 2.64262L15.2082 2.28906L14.8546 1.93551L5.89628 10.8938L6.24984 11.2474ZM15.2082 2.28906L14.8546 2.64262L17.3546 5.14262L17.7082 4.78906L18.0617 4.43551L15.5617 1.93551L15.2082 2.28906ZM17.7082 4.78906L17.3546 4.43551L8.39628 13.3938L8.74984 13.7474L9.10339 14.101L18.0617 5.14262L17.7082 4.78906Z" fill="currentColor"/>`,
  'pencil-line': `<path d="M9.58301 17.9166H17.9163M17.9163 5.83325L14.1663 2.08325L2.08301 14.1666V17.9166H5.83301L17.9163 5.83325Z" stroke="currentColor" stroke-linecap="square"/>`,

  // Brain/thinking
  brain: `<path d="M13.332 8.7487C11.4911 8.7487 9.9987 7.25631 9.9987 5.41536M6.66536 11.2487C8.50631 11.2487 9.9987 12.7411 9.9987 14.582M9.9987 2.78209L9.9987 17.0658M16.004 15.0475C17.1255 14.5876 17.9154 13.4849 17.9154 12.1978C17.9154 11.3363 17.5615 10.5575 16.9913 9.9987C17.5615 9.43991 17.9154 8.66108 17.9154 7.79962C17.9154 6.21199 16.7136 4.90504 15.1702 4.73878C14.7858 3.21216 13.4039 2.08203 11.758 2.08203C11.1171 2.08203 10.5162 2.25337 9.9987 2.55275C9.48117 2.25337 8.88032 2.08203 8.23944 2.08203C6.59353 2.08203 5.21157 3.21216 4.82722 4.73878C3.28377 4.90504 2.08203 6.21199 2.08203 7.79962C2.08203 8.66108 2.43585 9.43991 3.00609 9.9987C2.43585 10.5575 2.08203 11.3363 2.08203 12.1978C2.08203 13.4849 2.87191 14.5876 3.99339 15.0475C4.46688 16.7033 5.9917 17.9154 7.79962 17.9154C8.61335 17.9154 9.36972 17.6698 9.9987 17.2488C10.6277 17.6698 11.384 17.9154 12.1978 17.9154C14.0057 17.9154 15.5305 16.7033 16.004 15.0475Z" stroke="currentColor"/>`,

  // Copy
  copy: `<path d="M6.2513 6.24935V2.91602H17.0846V13.7493H13.7513M13.7513 6.24935V17.0827H2.91797V6.24935H13.7513Z" stroke="currentColor" stroke-linecap="round"/>`,

  // Stop
  stop: `<rect x="5" y="5" width="10" height="10" fill="currentColor"/>`,

  // Plus
  plus: `<path d="M9.9987 2.20703V9.9987M9.9987 9.9987V17.7904M9.9987 9.9987H2.20703M9.9987 9.9987H17.7904" stroke="currentColor" stroke-linecap="square"/>`,
  'plus-small': `<path d="M9.99984 5.41699V10.0003M9.99984 10.0003V14.5837M9.99984 10.0003H5.4165M9.99984 10.0003H14.5832" stroke="currentColor" stroke-linecap="square"/>`,

  // Settings
  'settings-gear': `<path d="M7.62516 4.46094L5.05225 3.86719L3.86475 5.05469L4.4585 7.6276L2.0835 9.21094V10.7943L4.4585 12.3776L3.86475 14.9505L5.05225 16.138L7.62516 15.5443L9.2085 17.9193H10.7918L12.3752 15.5443L14.9481 16.138L16.1356 14.9505L15.5418 12.3776L17.9168 10.7943V9.21094L15.5418 7.6276L16.1356 5.05469L14.9481 3.86719L12.3752 4.46094L10.7918 2.08594H9.2085L7.62516 4.46094Z" stroke="currentColor"/><path d="M12.5002 10.0026C12.5002 11.3833 11.3809 12.5026 10.0002 12.5026C8.61945 12.5026 7.50016 11.3833 7.50016 10.0026C7.50016 8.62189 8.61945 7.5026 10.0002 7.5026C11.3809 7.5026 12.5002 8.62189 12.5002 10.0026Z" stroke="currentColor"/>`,

  // Help
  help: `<path d="M7.91683 7.91927V6.2526H12.0835V8.7526L10.0002 10.0026V12.0859M10.0002 13.7526V13.7609M17.9168 10.0026C17.9168 14.3749 14.3724 17.9193 10.0002 17.9193C5.62791 17.9193 2.0835 14.3749 2.0835 10.0026C2.0835 5.63035 5.62791 2.08594 10.0002 2.08594C14.3724 2.08594 17.9168 5.63035 17.9168 10.0026Z" stroke="currentColor" stroke-linecap="square"/>`,

  // Download/Upload
  download: `<path d="M13.9583 10.6257L10 14.584L6.04167 10.6257M10 2.08398V13.959M16.25 17.9173H3.75" stroke="currentColor" stroke-linecap="square"/>`,
  share: `<path d="M10.0013 12.0846L10.0013 3.33464M13.7513 6.66797L10.0013 2.91797L6.2513 6.66797M17.0846 10.418V17.0846H2.91797V10.418" stroke="currentColor" stroke-linecap="square"/>`,

  // Expand/Collapse
  expand: `<path d="M4.58301 10.4163V15.4163H9.58301M10.4163 4.58301H15.4163V9.58301" stroke="currentColor" stroke-linecap="square"/>`,
  collapse: `<path d="M16.666 8.33398H11.666V3.33398" stroke="currentColor" stroke-linecap="square"/><path d="M8.33398 16.666V11.666H3.33398" stroke="currentColor" stroke-linecap="square"/>`,

  // Spinner (dash used for spinner animation)
  dash: `<rect x="5" y="9.5" width="10" height="1" fill="currentColor"/>`,

  // Photo
  photo: `<path d="M16.6665 16.6666L11.6665 11.6666L9.99984 13.3333L6.6665 9.99996L3.08317 13.5833M2.9165 2.91663H17.0832V17.0833H2.9165V2.91663ZM13.3332 7.49996C13.3332 8.30537 12.6803 8.95829 11.8748 8.95829C11.0694 8.95829 10.4165 8.30537 10.4165 7.49996C10.4165 6.69454 11.0694 6.04163 11.8748 6.04163C12.6803 6.04163 13.3332 6.69454 13.3332 7.49996Z" stroke="currentColor" stroke-linecap="square"/>`,

  // Menu
  menu: `<path d="M2.5 5H17.5M2.5 10H17.5M2.5 15H17.5" stroke="currentColor" stroke-linecap="square"/>`,

  // Server
  server: `<rect x="3.35547" y="1.92969" width="13.2857" height="16.1429" stroke="currentColor"/><rect x="3.35547" y="11.9297" width="13.2857" height="6.14286" stroke="currentColor"/><rect x="12.8555" y="14.2852" width="1.42857" height="1.42857" fill="currentColor"/><rect x="10" y="14.2852" width="1.42857" height="1.42857" fill="currentColor"/>`,

  // Knowledge graph / code graph (network nodes with connections)
  'knowledge-graph': `<circle cx="10" cy="4.5" r="2" stroke="currentColor" stroke-width="1.2"/><circle cx="4.5" cy="15" r="2" stroke="currentColor" stroke-width="1.2"/><circle cx="15.5" cy="15" r="2" stroke="currentColor" stroke-width="1.2"/><circle cx="17" cy="7" r="1.5" stroke="currentColor" stroke-width="1.2"/><circle cx="3" cy="7" r="1.5" stroke="currentColor" stroke-width="1.2"/><line x1="8.3" y1="5.7" x2="5.5" y2="6.3" stroke="currentColor" stroke-width="1.2"/><line x1="11.5" y1="5.9" x2="16" y2="7" stroke="currentColor" stroke-width="1.2"/><line x1="8.5" y1="6" x2="5.5" y2="13.5" stroke="currentColor" stroke-width="1.2"/><line x1="11.5" y1="6" x2="14.5" y2="13.5" stroke="currentColor" stroke-width="1.2"/><line x1="6.2" y1="15" x2="13.8" y2="15" stroke="currentColor" stroke-width="1.2"/>`,
};

export type IconName = keyof typeof icons;

export interface ToolIconProps {
  name: IconName;
  size?: 'small' | 'normal' | 'medium' | 'large';
  className?: string;
}

const sizeMap = {
  small: 14,
  normal: 16,
  medium: 18,
  large: 20,
};

export const ToolIcon: React.FC<ToolIconProps> = ({ name, size = 'normal', className }) => {
  const svgSize = sizeMap[size];
  const iconPath = icons[name] || icons.mcp;

  return (
    <div
      data-component='tool-icon'
      data-size={size}
      className={classNames('inline-flex items-center justify-center', className)}
    >
      <svg
        width={svgSize}
        height={svgSize}
        viewBox='0 0 20 20'
        fill='none'
        dangerouslySetInnerHTML={{ __html: iconPath }}
        aria-hidden='true'
        className='text-current'
      />
    </div>
  );
};

// Helper function to get tool icon name
export function getToolIconName(tool: string): IconName {
  switch (tool) {
    case 'read':
      return 'glasses';
    case 'list':
      return 'bullet-list';
    case 'glob':
    case 'grep':
      return 'magnifying-glass-menu';
    case 'bash':
    case 'shell':
    case 'command':
      return 'console';
    case 'edit':
    case 'write':
    case 'apply_patch':
      return 'code-lines';
    case 'task':
    case 'delegate':
      return 'task';
    case 'todowrite':
    case 'todoread':
      return 'checklist';
    case 'webfetch':
    case 'web':
      return 'window-cursor';
    case 'question':
      return 'bubble-5';
    case 'skill':
      return 'brain';
    case 'kb_codegraph_explore':
    case 'kb_codegraph_call_chain':
    case 'kb_codegraph_class_hierarchy':
      return 'knowledge-graph';
    case 'kb_ls':
      return 'bullet-list';
    case 'kb_glob':
    case 'kb_grep':
      return 'magnifying-glass-menu';
    case 'kb_cat':
      return 'glasses';
    case 'semantic_search':
      return 'brain';
    default:
      return 'mcp';
  }
}

// Status text mapping
export const STATUS_TEXT_MAP: Record<string, string> = {
  task: 'Delegating...',
  todowrite: 'Planning...',
  todoread: 'Planning...',
  read: 'Gathering context...',
  list: 'Searching codebase...',
  grep: 'Searching codebase...',
  glob: 'Searching codebase...',
  webfetch: 'Searching web...',
  edit: 'Making edits...',
  write: 'Making edits...',
  apply_patch: 'Making edits...',
  bash: 'Running commands...',
  reasoning: 'Thinking...',
  text: 'Gathering thoughts...',
  skill: 'Loading skill...',
  kb_codegraph_explore: 'Exploring code graph...',
  kb_codegraph_call_chain: 'Tracing call chain...',
  kb_codegraph_class_hierarchy: 'Tracing class hierarchy...',
  kb_ls: 'Listing files...',
  kb_glob: 'Finding files...',
  kb_grep: 'Searching content...',
  kb_cat: 'Reading file...',
  semantic_search: 'Searching semantically...',
};

export function getStatusText(tool: string): string {
  return STATUS_TEXT_MAP[tool] || 'Processing...';
}

export default ToolIcon;
