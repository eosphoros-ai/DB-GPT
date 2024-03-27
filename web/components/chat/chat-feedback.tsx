import React, { useState, useRef, useCallback, useEffect, useContext } from 'react';
import { MoreHoriz, CloseRounded } from '@mui/icons-material';
import {
  MenuButton,
  Button,
  Menu,
  MenuItem,
  Dropdown,
  Box,
  Grid,
  IconButton,
  Slider,
  Select,
  Option,
  Textarea,
  Typography,
  styled,
  Sheet,
} from '@mui/joy';
import { message, Tooltip } from 'antd';
import { apiInterceptors, getChatFeedBackItme, postChatFeedBackForm } from '@/client/api';
import { ChatContext } from '@/app/chat-context';
import { ChatFeedBackSchema } from '@/types/db';
import { useTranslation } from 'react-i18next';
import { FeedBack } from '@/types/chat';

type Props = {
  conv_index: number;
  question: any;
  knowledge_space: string;
  select_param?: FeedBack;
};

const ChatFeedback = ({ conv_index, question, knowledge_space, select_param }: Props) => {
  const { t } = useTranslation();
  const { chatId } = useContext(ChatContext);
  const [ques_type, setQuesType] = useState('');
  const [score, setScore] = useState(4);
  const [text, setText] = useState('');
  const action = useRef(null);
  const [messageApi, contextHolder] = message.useMessage();

  const handleOpenChange = useCallback(
    (event: any, isOpen: boolean) => {
      if (isOpen) {
        apiInterceptors(getChatFeedBackItme(chatId, conv_index))
          .then((res) => {
            const finddata = res[1] ?? {};
            setQuesType(finddata.ques_type ?? '');
            setScore(parseInt(finddata.score ?? '4'));
            setText(finddata.messages ?? '');
          })
          .catch((err) => {
            console.log(err);
          });
      } else {
        setQuesType('');
        setScore(4);
        setText('');
      }
    },
    [chatId, conv_index],
  );

  const marks = [
    { value: 0, label: '0' },
    { value: 1, label: '1' },
    { value: 2, label: '2' },
    { value: 3, label: '3' },
    { value: 4, label: '4' },
    { value: 5, label: '5' },
  ];
  function valueText(value: number) {
    return {
      0: t('Lowest'),
      1: t('Missed'),
      2: t('Lost'),
      3: t('Incorrect'),
      4: t('Verbose'),
      5: t('Best'),
    }[value];
  }
  const Item = styled(Sheet)(({ theme }) => ({
    backgroundColor: theme.palette.mode === 'dark' ? '#FBFCFD' : '#0E0E10',
    ...theme.typography['body-sm'],
    padding: theme.spacing(1),
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 4,
    width: '100%',
    height: '100%',
  }));
  const handleSubmit = (event: any) => {
    event.preventDefault();
    const formData: ChatFeedBackSchema = {
      conv_uid: chatId,
      conv_index: conv_index,
      question: question,
      knowledge_space: knowledge_space,
      score: score,
      ques_type: ques_type,
      messages: text,
    };
    console.log(formData);
    apiInterceptors(
      postChatFeedBackForm({
        data: formData,
      }),
    )
      .then((res) => {
        messageApi.open({ type: 'success', content: 'save success' });
      })
      .catch((err) => {
        messageApi.open({ type: 'error', content: 'save error' });
      });
  };
  return (
    <Dropdown onOpenChange={handleOpenChange}>
      {contextHolder}
      <Tooltip title={t('Rating')}>
        <MenuButton slots={{ root: IconButton }} slotProps={{ root: { variant: 'plain', color: 'primary' } }} sx={{ borderRadius: 40 }}>
          <MoreHoriz />
        </MenuButton>
      </Tooltip>
      <Menu>
        <MenuItem disabled sx={{ minHeight: 0 }} />
        <Box
          sx={{
            width: '100%',
            maxWidth: 350,
            display: 'grid',
            gap: 3,
            padding: 1,
          }}
        >
          <form onSubmit={handleSubmit}>
            <Grid container spacing={0.5} columns={13} sx={{ flexGrow: 1 }}>
              <Grid xs={3}>
                <Item>{t('Q_A_Category')}</Item>
              </Grid>
              <Grid xs={10}>
                <Select
                  action={action}
                  value={ques_type}
                  placeholder="Choose one…"
                  onChange={(event, newValue) => setQuesType(newValue ?? '')}
                  {...(ques_type && {
                    // display the button and remove select indicator
                    // when user has selected a value
                    endDecorator: (
                      <IconButton
                        size="sm"
                        variant="plain"
                        color="neutral"
                        onMouseDown={(event) => {
                          // don't open the popup when clicking on this button
                          event.stopPropagation();
                        }}
                        onClick={() => {
                          setQuesType('');
                          action.current?.focusVisible();
                        }}
                      >
                        <CloseRounded />
                      </IconButton>
                    ),
                    indicator: null,
                  })}
                  sx={{ width: '100%' }}
                >
                  {select_param &&
                    Object.keys(select_param)?.map((paramItem) => (
                      <Option key={paramItem} value={paramItem}>
                        {select_param[paramItem]}
                      </Option>
                    ))}
                </Select>
              </Grid>
              <Grid xs={3}>
                <Item>
                  <Tooltip
                    title={
                      <Box>
                        <div>{t('feed_back_desc')}</div>
                      </Box>
                    }
                    variant="solid"
                    placement="left"
                  >
                    {t('Q_A_Rating')}
                  </Tooltip>
                </Item>
              </Grid>
              <Grid xs={10} sx={{ pl: 0, ml: 0 }}>
                <Slider
                  aria-label="Custom"
                  step={1}
                  min={0}
                  max={5}
                  valueLabelFormat={valueText}
                  valueLabelDisplay="on"
                  marks={marks}
                  sx={{ width: '90%', pt: 3, m: 2, ml: 1 }}
                  onChange={(event) => setScore(event.target?.value)}
                  value={score}
                />
              </Grid>
              <Grid xs={13}>
                <Textarea
                  placeholder={t('Please_input_the_text')}
                  value={text}
                  onChange={(event) => setText(event.target.value)}
                  minRows={2}
                  maxRows={4}
                  endDecorator={
                    <Typography level="body-xs" sx={{ ml: 'auto' }}>
                      {t('input_count') + text.length + t('input_unit')}
                    </Typography>
                  }
                  sx={{ width: '100%', fontSize: 14 }}
                />
              </Grid>
              <Grid xs={13}>
                <Button type="submit" variant="outlined" sx={{ width: '100%', height: '100%' }}>
                  {t('submit')}
                </Button>
              </Grid>
            </Grid>
          </form>
        </Box>
      </Menu>
    </Dropdown>
  );
};
export default ChatFeedback;
