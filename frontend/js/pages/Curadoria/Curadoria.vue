<script setup lang="ts">

import Layout from '@/components/Layout.vue';
import { PerguntaCanonica } from '@/types/index';

import { usePage, Link } from '@inertiajs/vue3';
const page = usePage<{
    urls: Record<string, string>,
}>();

defineProps<{
    respostas_canonicas: PerguntaCanonica[];
}>();

</script>

<template>
    <Layout>
        <div class="max-w-3xl mx-auto space-y-4 p-4 w-full">
            <Link class="btn btn-primary mb-4" :href="page.props['urls']['cadastro_canonica']">Inserir</Link>

            <div class="flex flex-col gap-3">

                <div class="collapse bg-base-100 border border-base-300" v-for="pergunta in respostas_canonicas"
                    :key="pergunta.id">
                    <input type="radio" name="my-accordion-1" />
                    <div class="collapse-title font-semibold flex justify-between p-4">
                        <span>{{ pergunta.pergunta }}</span>
                    </div>
                    <div class="collapse-content text-sm flex justify-between ">{{ pergunta.resposta }}
                        <div class="flex gap-4 ml-4 items-center">
    
                            <Link method="post"
                                :href="page.props['urls']['excluir_canonica'].replace('%(id_canonica)s', pergunta.id.toString())">
                                <i class="bi bi-trash3-fill text-error"></i>
                            </Link>
    
                            <Link method="get"
                                :href="page.props.urls.editar_canonica.replace('%(id_canonica)s', pergunta.id.toString())">
                                <i class="bi bi-pencil"></i>
                            </Link>
                        </div>
                    </div>
                </div>

            </div>

        </div>
    </Layout>
</template>