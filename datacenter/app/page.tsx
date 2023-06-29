"use client";
import { useRequest } from 'ahooks';
import { useState } from 'react';
import { Button, Input, useColorScheme } from '@/lib/mui';
import IconButton from '@mui/joy/IconButton';
import SendRoundedIcon from '@mui/icons-material/SendRounded';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { sendPostRequest } from '@/utils/request';
import { useRouter } from 'next/navigation';

export default function Home() {
  const Schema = z.object({ query: z.string().min(1) });
  const router = useRouter();
  const { mode } = useColorScheme();
  const [isLoading, setIsLoading] = useState(false);
  const methods = useForm<z.infer<typeof Schema>>({
    resolver: zodResolver(Schema),
    defaultValues: {},
  });
  const { data: scenesList } = useRequest(async () => await sendPostRequest('v1/chat/dialogue/scenes'));

  const submit = async ({ query }: z.infer<typeof Schema>) => {
    try {
      setIsLoading(true);
      methods.reset();
      const res = await sendPostRequest('/v1/chat/dialogue/new', {
        chat_mode: 'chat_normal'
      });
      if (res?.success && res?.data?.conv_uid) {
        router.push(`/agents/${res?.data?.conv_uid}?initMessage=${query}`);
      }
    } catch (err) {
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <> 
      <div className={`${mode} absolute z-20 top-0 inset-x-0 flex justify-center overflow-hidden pointer-events-none`}>
        <div className='w-[108rem] flex-none flex justify-end'>
          <picture>
            <source srcSet='/bg1.avif' type='image/avif'></source>
            <img srcSet='/bg2.png' alt="" className='w-[71.75rem] flex-none max-w-none '/>
          </picture>
        </div>
      </div>
      <div className='mx-auto flex h-full max-w-3xl flex-col gap-6 px-5 pt-6 sm:gap-8 xl:max-w-4xl'>
        <div className='lg:my-auto grid gap-8 lg:grid-cols-3'>
          <div className='lg:col-span-3 lg:mt-12'>
            <p className='mb-3'>Scenes</p>
            <div className='grid gap-2 lg:grid-cols-3 lg:gap-4'>
              {scenesList?.data?.map(scene => (
                <Button
                  key={scene['chat_scene']}
                  size="md"
                  variant="soft"
                  onClick={async () => {
                    const res = await sendPostRequest('/v1/chat/dialogue/new', {
                      chat_mode: scene['chat_scene']
                    });
                    if (res?.success && res?.data?.conv_uid) {
                      router.push(`/agents/${res?.data?.conv_uid}?scene=${scene['chat_scene']}`);
                    }
                  }}
                >
                  {scene['scene_name']
                }</Button>
              ))}
            </div>
          </div>
        </div>
        <div className='h-60 flex-none'></div>
      </div>
      <div className='pointer-events-none absolute inset-x-0 bottom-0 z-0 mx-auto flex w-full max-w-3xl flex-col items-center justify-center px-3.5 py-4 max-md:border-t sm:px-5 md:py-8 xl:max-w-4xl [&>*]:pointer-events-auto'>
        <form
          style={{
            maxWidth: '100%',
            width: '100%',
            position: 'relative',
            display: 'flex',
            marginTop: 'auto',
            overflow: 'visible',
            background: 'none',
            justifyContent: 'center',
            marginLeft: 'auto',
            marginRight: 'auto',
          }}
          onSubmit={(e) => {
            methods.handleSubmit(submit)(e);
          }}
        >
          <Input
            sx={{ width: '100%' }}
            variant="outlined"
            placeholder='Ask anything'
            endDecorator={
              <IconButton type="submit" disabled={isLoading}>
                <SendRoundedIcon />
              </IconButton>
            }
            {...methods.register('query')}
          />
        </form>
      </div>
    </>
    
  )
}
